#!/usr/bin/env bash
# Download the built web UI (web-dist.tar.gz) from a GitHub Release into web/dist.
#   scripts/fetch_web.sh            latest release
#   scripts/fetch_web.sh --tag v0.1.0
# No jq dependency: the JSON is parsed with python3 (always present on the Pi).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
REPO="${PLANT_REPO:-xparapx/Plant_Growth_Monitoring_Demo}"
TAG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag) TAG="$2"; shift 2 ;;
    *) echo "unknown arg $1" >&2; exit 2 ;;
  esac
done
if [[ -z "$TAG" ]]; then
  TAG="$(git -C "$ROOT" describe --tags --exact-match 2>/dev/null || true)"
fi
API="https://api.github.com/repos/$REPO/releases/latest"
[[ -n "$TAG" ]] && API="https://api.github.com/repos/$REPO/releases/tags/$TAG"

CACHE="$ROOT/web/.cache"
mkdir -p "$CACHE"
echo "[fetch_web] $API"
JSON="$(curl -fsSL -H 'Accept: application/vnd.github+json' "$API")"
URLS="$(printf '%s' "$JSON" | python3 -c '
import json,sys
d=json.load(sys.stdin)
a={x["name"]:x["browser_download_url"] for x in d.get("assets",[])}
print(a.get("web-dist.tar.gz",""), a.get("web-dist.tar.gz.sha256",""), d.get("tag_name",""))
')"
read -r TAR SHA REL <<<"$URLS"
if [[ -z "$TAR" ]]; then
  echo "[fetch_web] release $REL has no web-dist.tar.gz asset" >&2
  exit 1
fi
curl -fsSL -o "$CACHE/web-dist.tar.gz" "$TAR"
if [[ -n "$SHA" ]]; then
  curl -fsSL -o "$CACHE/web-dist.tar.gz.sha256" "$SHA"
  (cd "$CACHE" && sha256sum -c web-dist.tar.gz.sha256)
fi
rm -rf "$ROOT/web/dist"
mkdir -p "$ROOT/web"
tar -xzf "$CACHE/web-dist.tar.gz" -C "$ROOT/web"
echo "$REL" > "$ROOT/web/dist/VERSION"
echo "[fetch_web] web/dist <- $REL"
