#!/usr/bin/env bash
# Roll the Pi back to a previous git ref and (optionally) the Streamlit dashboard.
#   scripts/rollback.sh <sha|tag> [--streamlit]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"
REF="${1:?git ref required}"; shift || true
ST=0; [[ "${1:-}" == "--streamlit" ]] && ST=1
echo "rolling back to $REF (current: $(git rev-parse --short HEAD))"
sudo systemctl disable --now plantsvc.service plantsnap-catchup.service 2>/dev/null || true
git fetch --tags --quiet
git checkout --quiet "$REF"
if [[ $ST -eq 1 ]]; then
  scripts/install.sh --update --legacy --web=skip
  sudo systemctl enable --now plantdash.service
  echo "Streamlit dashboard: http://$(hostname):8501"
else
  scripts/install.sh --update --web=skip
fi
