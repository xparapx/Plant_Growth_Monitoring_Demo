<#
.SYNOPSIS
  PC -> Pi deployment: push the current branch, pull it on the Pi, run scripts/install.sh --update, check health.
.EXAMPLE
  .\scripts\deploy.ps1                       # host 'raspi', web from the latest GitHub release
  .\scripts\deploy.ps1 -Web local            # build web/ here and upload web-dist.tar.gz (no release needed)
  .\scripts\deploy.ps1 -PiHost raspi -Full   # full install (apt etc.)
.NOTES
  Windows PowerShell 5.1 compatible (no &&, no ternary). Requires key-based ssh to the Pi (see manual §9).
#>
[CmdletBinding()]
param(
  [string]$PiHost = "raspi",
  [string]$RemoteDir = "~/plant",
  [string]$Branch = "",
  [ValidateSet("release", "local", "skip", "build")][string]$Web = "release",
  [switch]$NoPush,
  [switch]$Full,
  [switch]$Force
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

function Invoke-Native([string]$cmd, [string[]]$argv) {
  & $cmd @argv
  if ($LASTEXITCODE -ne 0) { throw "$cmd $($argv -join ' ') failed ($LASTEXITCODE)" }
}

# 1. preflight
$dirty = git status --porcelain
if ($dirty -and -not $Force) { throw "working tree is dirty - commit first (or -Force)" }
if (-not $Branch) { $Branch = (git rev-parse --abbrev-ref HEAD).Trim() }
Write-Host "== deploy $Branch -> $PiHost:$RemoteDir (web=$Web)"
& ssh -o BatchMode=yes -o ConnectTimeout=8 $PiHost "true"
if ($LASTEXITCODE -ne 0) {
  Write-Host "ssh key login to $PiHost failed. One-time setup (enter the Pi password once):"
  Write-Host '  type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh jh@raspi "mkdir -p ~/.ssh && chmod 700 ~/.ssh && tr -d ''\r'' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"'
  exit 2
}

# 2. push
if (-not $NoPush) { Invoke-Native "git" @("push", "origin", $Branch) }

# 3. optional local web build + upload
if ($Web -eq "local") {
  if (-not (Test-Path "web\node_modules")) { Push-Location web; Invoke-Native "npm" @("ci", "--no-audit", "--no-fund"); Pop-Location }
  Push-Location web; Invoke-Native "npm" @("run", "build"); Pop-Location
  $tar = Join-Path $env:TEMP "web-dist.tar.gz"
  if (Test-Path $tar) { Remove-Item $tar -Force }
  Invoke-Native "tar.exe" @("-czf", $tar, "-C", "web", "dist")
  Invoke-Native "ssh" @($PiHost, "mkdir -p $RemoteDir/web")
  Invoke-Native "scp" @("-q", $tar, "${PiHost}:$RemoteDir/web/web-dist.tar.gz")
  Write-Host "uploaded web-dist.tar.gz"
}

# 4. remote update (single quoted command line; no stdin piping -> no CRLF risk)
$prev = (& ssh $PiHost "cd $RemoteDir && git rev-parse --short HEAD 2>/dev/null").Trim()
$mode = "--update"
if ($Full) { $mode = "" }
$remote = "cd $RemoteDir && git fetch --prune --quiet && git checkout --quiet $Branch && git pull --ff-only --quiet && scripts/install.sh $mode --web=$Web"
& ssh $PiHost $remote
if ($LASTEXITCODE -ne 0) {
  Write-Host "remote install failed. Logs:  ssh $PiHost 'journalctl -u plantsvc -n 50 --no-pager'"
  if ($prev) { Write-Host "rollback:  ssh $PiHost 'cd $RemoteDir && scripts/rollback.sh $prev'" }
  exit 1
}

# 5. health
& ssh $PiHost "cd $RemoteDir && .venv/bin/plantsvc doctor --brief; systemctl --no-pager --no-legend list-timers plantsnap.timer"
try {
  $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 8 "http://${PiHost}:8080/api/system/status"
  $j = $r.Content | ConvertFrom-Json
  Write-Host ("== OK  version={0} git={1} camera={2} dummy_fill={3}  http://{4}:8080/" -f $j.version, $j.git_rev, $j.camera.driver, $j.dummy_fill, $PiHost)
} catch {
  Write-Host "health check failed: $_"
  exit 1
}
