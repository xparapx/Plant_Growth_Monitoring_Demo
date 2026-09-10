#!/usr/bin/env bash
# Render deploy/systemd/*.tmpl with THIS user / THIS checkout / THIS config.json.
#   scripts/render_units.sh [--out DIR]      -> deploy/systemd/rendered/ by default
# Thin wrapper around `plantsvc render-units` (needs the venv from install.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
PY="$ROOT/.venv/bin/plantsvc"
if [[ ! -x "$PY" ]]; then
  echo "no .venv yet - run scripts/install.sh first" >&2
  exit 1
fi
exec "$PY" render-units --root "$ROOT" --user "$(id -un)" "$@"
