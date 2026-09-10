#!/usr/bin/env bash
# Move a legacy flattened ~/plant (hub/ files + plant.db + photos/ in one dir) into the new
# git-clone layout: <repo>/data/. COPIES ONLY - never deletes the source.
#
#   scripts/migrate_legacy.sh [--from DIR] [--dry-run]
#
# Typical: the old install lives at ~/plant and you want the new clone there too:
#   mv ~/plant ~/plant.legacy-$(date +%Y%m%d)
#   git clone https://github.com/xparapx/Plant_Growth_Monitoring_Demo.git ~/plant
#   cd ~/plant && scripts/migrate_legacy.sh --from ~/plant.legacy-YYYYMMDD && scripts/install.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
FROM=""; DRY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --from) FROM="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    *) echo "unknown arg $1" >&2; exit 2 ;;
  esac
done
if [[ -z "$FROM" ]]; then
  for c in "$HOME"/plant.legacy-* /home/*/plant; do
    [[ -f "$c/plant.db" || -f "$c/run_collector.py" ]] && [[ ! -d "$c/.git" ]] && { FROM="$c"; break; }
  done
fi
if [[ -z "$FROM" || ! -d "$FROM" ]]; then
  echo "no legacy directory found (fresh install) — nothing to migrate"; exit 0
fi
DATA="${PLANT_DATA_DIR:-$ROOT/data}"
echo "legacy: $FROM"
echo "target: $DATA"
for u in plantsnap.timer plantdash.service plantcam.service; do
  systemctl is-enabled "$u" >/dev/null 2>&1 && echo "  old unit enabled: $u (install.sh disables the legacy ones)"
done
if [[ $DRY -eq 1 ]]; then
  "$ROOT/.venv/bin/plantsvc" migrate-data --from "$FROM" --dry-run 2>/dev/null || python3 - "$FROM" "$DATA" <<'EOF'
import os, sys
src, dst = sys.argv[1], sys.argv[2]
for n in ("plant.db", "config.json", "calib.jpg", "truth.json", "photos"):
    if os.path.exists(os.path.join(src, n)): print(f"  {os.path.join(src, n)}  ->  {os.path.join(dst, n)}")
EOF
  exit 0
fi
mkdir -p "$DATA"
if [[ -x "$ROOT/.venv/bin/plantsvc" ]]; then
  "$ROOT/.venv/bin/plantsvc" migrate-data --from "$FROM"
else
  # venv not built yet: plain copies (sqlite backup happens on the next run of install.sh's doctor)
  for n in plant.db config.json calib.jpg truth.json; do [[ -f "$FROM/$n" ]] && cp -an "$FROM/$n" "$DATA/"; done
  [[ -d "$FROM/photos" ]] && cp -an "$FROM/photos" "$DATA/"
fi
if [[ "$(stat -c %U "$DATA")" != "$(id -un)" ]]; then sudo chown -R "$(id -u):$(id -g)" "$DATA"; fi
{
  echo "migrated_from=$FROM"; echo "at=$(date -Is)"
  [[ -f "$DATA/plant.db" ]] && python3 -c "import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);print(*(f'{t}={c.execute(f\"select count(*) from {t}\").fetchone()[0]}' for t in ('readings','soil','pump_log','growth')))" "$DATA/plant.db"
} | tee "$DATA/MIGRATED_FROM.txt"
echo "next: scripts/install.sh   (the legacy dir is kept; delete it yourself after the checklist passes)"
