#!/usr/bin/env bash
# Plant hub installer / updater for a Raspberry Pi (or any Debian-ish SBC).
#
#   git clone https://github.com/xparapx/Plant_Growth_Monitoring_Demo.git ~/plant
#   cd ~/plant && scripts/install.sh                 # fresh install
#   scripts/install.sh --update                      # after git pull (auto when .venv exists)
#
# Options
#   --update              skip apt, keep venv, restart services
#   --web=release|local|build|skip   how to get web/dist (default: release, falls back to build, then skip)
#   --tag vX.Y.Z          release tag for --web=release
#   --data-dir DIR        PLANT_DATA_DIR (default <repo>/data)
#   --set-timezone        run timedatectl set-timezone <config tz>
#   --no-apt --no-enable --legacy --dry-run
#
# Nothing here is user- or host-specific: the systemd units are rendered from templates with
# `id -un`, this checkout's path and config.json (schedule, LED warm-up).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"
UPDATE=0; WEB="release"; TAG=""; DATA_DIR="${PLANT_DATA_DIR:-$ROOT/data}"; SET_TZ=0; NO_APT=0; NO_ENABLE=0; LEGACY=0; DRY=0
for a in "$@"; do
  case "$a" in
    --update) UPDATE=1 ;;
    --web=*) WEB="${a#--web=}" ;;
    --tag) : ;;
    --data-dir=*) DATA_DIR="${a#--data-dir=}" ;;
    --set-timezone) SET_TZ=1 ;;
    --no-apt) NO_APT=1 ;;
    --no-enable) NO_ENABLE=1 ;;
    --legacy) LEGACY=1 ;;
    --dry-run) DRY=1 ;;
    v*) TAG="$a" ;;
    --data-dir|--tag) ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done
# two-token forms (--tag vX, --data-dir DIR)
prev=""
for a in "$@"; do
  [[ "$prev" == "--tag" ]] && TAG="$a"
  [[ "$prev" == "--data-dir" ]] && DATA_DIR="$a"
  prev="$a"
done
[[ -d .venv && $UPDATE -eq 0 && "${1:-}" != "--fresh" ]] && UPDATE=1
export PLANT_DATA_DIR="$DATA_DIR"

STEP=0; TOTAL=12
step() { STEP=$((STEP + 1)); echo; echo "[$STEP/$TOTAL] $1"; }
trap 'echo; echo "FAILED at step $STEP (see above). Log: $DATA_DIR/install.log"' ERR
mkdir -p "$DATA_DIR"
exec > >(tee -a "$DATA_DIR/install.log") 2>&1
echo "== install.sh $(date -Is)  update=$UPDATE web=$WEB data=$DATA_DIR user=$(id -un) root=$ROOT"

step "preflight"
[[ "$(id -u)" -eq 0 ]] && { echo "run as the service user, not root"; exit 1; }
ON_PI=0; [[ -f /proc/device-tree/model ]] && ON_PI=1 && tr -d '\0' </proc/device-tree/model && echo
git -C "$ROOT" rev-parse --short HEAD >/dev/null 2>&1 || echo "  (not a git checkout — updates via git pull will not work)"
HAVE_SUDO=0; sudo -n true 2>/dev/null && HAVE_SUDO=1
[[ $HAVE_SUDO -eq 0 ]] && echo "  sudo needs a password here: system steps will print the commands for you to run"
[[ $DRY -eq 1 ]] && { echo "dry run: stopping after preflight"; exit 0; }

step "apt packages (picamera2, gpiozero/lgpio, mosquitto)"
if [[ $NO_APT -eq 1 || $UPDATE -eq 1 ]]; then
  echo "  skipped"
elif [[ $HAVE_SUDO -eq 1 ]]; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3-picamera2 python3-gpiozero python3-lgpio mosquitto mosquitto-clients git rpicam-apps || \
    sudo apt-get install -y -qq python3-picamera2 python3-gpiozero mosquitto mosquitto-clients git
else
  echo "  run: sudo apt-get install -y python3-picamera2 python3-gpiozero python3-lgpio mosquitto mosquitto-clients git rpicam-apps"
fi

step "uv"
if ! command -v uv >/dev/null 2>&1 && [[ ! -x "$HOME/.local/bin/uv" ]]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
echo "  $($UV --version)"

step "python venv (system site-packages so apt's picamera2/gpiozero are visible)"
# ★ Always the SYSTEM interpreter, for venv AND sync: if uv is left to pick a managed CPython
#   (e.g. from .python-version) it silently recreates .venv without system site-packages and
#   picamera2/gpiozero vanish. UV_PYTHON pins it for every uv call in this script.
export UV_PYTHON=/usr/bin/python3
if [[ ! -f .venv/pyvenv.cfg ]] || ! grep -q 'include-system-site-packages = true' .venv/pyvenv.cfg; then
  rm -rf .venv
  "$UV" venv --system-site-packages --python /usr/bin/python3
fi
SYNC_ARGS=(--frozen --no-dev --python /usr/bin/python3)
[[ $LEGACY -eq 1 ]] && SYNC_ARGS+=(--extra legacy)
"$UV" sync "${SYNC_ARGS[@]}"
grep -q 'include-system-site-packages = true' .venv/pyvenv.cfg || { echo "venv lost system-site-packages"; exit 1; }
if [[ $ON_PI -eq 1 ]]; then
  .venv/bin/python -c 'import picamera2, cv2, fastapi; print("  picamera2 + cv2 + fastapi OK")' || {
    echo "  picamera2 not importable in the venv — check apt python3-picamera2 and numpy ABI (see manual)"; exit 1; }
else
  .venv/bin/python -c 'import cv2, fastapi; print("  cv2 + fastapi OK (no camera on this host)")'
fi

step "data dir + config"
mkdir -p "$DATA_DIR/photos/raw" "$DATA_DIR/photos/mask" "$DATA_DIR/photos/debug"
if [[ ! -f "$DATA_DIR/config.json" ]]; then
  cp hub/config.example.json "$DATA_DIR/config.json"
  echo "  seeded $DATA_DIR/config.json from hub/config.example.json"
fi
[[ -f "$DATA_DIR/calib.jpg" ]] || echo "  (no calib.jpg yet — finish the camera setup in the web UI)"
[[ -f "$DATA_DIR/plant.db" ]] || echo "  (no plant.db yet — created by planthub on first MQTT message; dashboard shows DUMMY DATA until then)"

step "mosquitto config"
if [[ $HAVE_SUDO -eq 1 ]] && command -v mosquitto >/dev/null 2>&1; then
  if ! cmp -s hub/plant.conf /etc/mosquitto/conf.d/plant.conf 2>/dev/null; then
    sudo install -m 0644 hub/plant.conf /etc/mosquitto/conf.d/plant.conf
    sudo systemctl restart mosquitto
  fi
  sudo systemctl enable mosquitto >/dev/null 2>&1 || true
else
  echo "  run: sudo cp hub/plant.conf /etc/mosquitto/conf.d/ && sudo systemctl restart mosquitto"
fi

step "web UI (web/dist)"
case "$WEB" in
  release)
    if scripts/fetch_web.sh ${TAG:+--tag "$TAG"}; then :; elif command -v node >/dev/null 2>&1; then
      echo "  release fetch failed — building locally"; (cd web && npm ci --no-audit --no-fund && npm run build)
    else echo "  WARN: no release asset and no node — the API serves a fallback page until web/dist exists"; fi ;;
  local)
    if [[ -f web/web-dist.tar.gz ]]; then rm -rf web/dist; tar -xzf web/web-dist.tar.gz -C web; echo "  extracted web/web-dist.tar.gz"
    else echo "  WARN: web/web-dist.tar.gz not found (deploy.ps1 -Web local uploads it)"; fi ;;
  build)
    command -v node >/dev/null 2>&1 || { echo "  node not installed"; exit 1; }
    (cd web && npm ci --no-audit --no-fund && npm run build) ;;
  skip) echo "  skipped" ;;
  *) echo "bad --web value"; exit 2 ;;
esac
[[ -f web/dist/index.html ]] && echo "  web/dist OK ($(cat web/dist/VERSION 2>/dev/null || echo local))" || echo "  WARN: web/dist/index.html missing"

step "systemd units (rendered from deploy/systemd/*.tmpl)"
.venv/bin/plantsvc render-units --root "$ROOT" --user "$(id -un)" --out deploy/systemd/rendered >/dev/null
( cd deploy/systemd/rendered && sha256sum * > .sha256.new )
CHANGED=1
if [[ -f deploy/systemd/rendered/.sha256 ]] && cmp -s deploy/systemd/rendered/.sha256 deploy/systemd/rendered/.sha256.new; then CHANGED=0; fi
mv deploy/systemd/rendered/.sha256.new deploy/systemd/rendered/.sha256
if command -v systemctl >/dev/null 2>&1; then
  if [[ $HAVE_SUDO -eq 1 ]]; then
    if [[ $CHANGED -eq 1 || ! -f /etc/systemd/system/plantsvc.service ]]; then
      for f in deploy/systemd/rendered/*.service deploy/systemd/rendered/*.timer; do sudo install -m 0644 "$f" /etc/systemd/system/; done
      if [[ -f /etc/systemd/system/plantsnap.service.d/camera-lock.conf ]]; then
        mkdir -p "$DATA_DIR/backup/etc"; sudo cp /etc/systemd/system/plantsnap.service.d/camera-lock.conf "$DATA_DIR/backup/etc/"
        sudo rm -f /etc/systemd/system/plantsnap.service.d/camera-lock.conf
        echo "  removed legacy camera-lock.conf drop-in (backup in $DATA_DIR/backup/etc)"
      fi
      sudo systemctl daemon-reload
      echo "  installed: $(ls deploy/systemd/rendered | tr '\n' ' ')"
    else echo "  unchanged"; fi
  else
    echo "  run: sudo install -m 0644 deploy/systemd/rendered/* /etc/systemd/system/ && sudo systemctl daemon-reload"
  fi
else
  echo "  no systemd on this host — rendered to deploy/systemd/rendered/ only"
fi

step "enable / start services"
if [[ $NO_ENABLE -eq 1 || ! -x "$(command -v systemctl || true)" ]]; then
  echo "  skipped"
elif [[ $HAVE_SUDO -eq 1 ]]; then
  sudo systemctl disable --now plantdash.service plantcam.service mjpeg.service 2>/dev/null || true
  sudo systemctl enable --now planthub.service plantsvc.service plantsnap.timer plantsnap-catchup.service
  if [[ $UPDATE -eq 1 ]]; then sudo systemctl restart planthub.service plantsvc.service; fi
  sudo systemctl enable --now systemd-time-wait-sync.service 2>/dev/null || true
  systemctl --no-pager --no-legend list-timers plantsnap.timer || true
else
  echo "  run: sudo systemctl enable --now planthub plantsvc plantsnap.timer plantsnap-catchup"
fi

step "timezone / clock"
TZ_WANT="$(.venv/bin/python -c 'import json,os;print(json.load(open(os.environ["PLANT_DATA_DIR"]+"/config.json")).get("tz","Asia/Seoul"))')"
if command -v timedatectl >/dev/null 2>&1; then
  TZ_NOW="$(timedatectl show -p Timezone --value 2>/dev/null || echo ?)"
  if [[ "$TZ_NOW" != "$TZ_WANT" ]]; then
    if [[ $SET_TZ -eq 1 && $HAVE_SUDO -eq 1 ]]; then sudo timedatectl set-timezone "$TZ_WANT"; echo "  timezone -> $TZ_WANT"
    else echo "  WARN: system tz is $TZ_NOW but config.json says $TZ_WANT — timers fire in the system tz. Fix: sudo timedatectl set-timezone $TZ_WANT"; fi
  else echo "  tz $TZ_NOW"; fi
fi

step "groups (video, gpio)"
for g in video gpio; do
  if getent group "$g" >/dev/null && ! id -nG | grep -qw "$g"; then
    if [[ $HAVE_SUDO -eq 1 ]]; then sudo usermod -aG "$g" "$(id -un)"; echo "  added to $g (re-login for shells; services already use SupplementaryGroups)"
    else echo "  run: sudo usermod -aG $g $(id -un)"; fi
  fi
done

step "doctor"
.venv/bin/plantsvc doctor || true
echo
echo "== done. UI: http://$(hostname):${PLANT_PORT:-8080}/   (camera setup: /camera/setup)"
