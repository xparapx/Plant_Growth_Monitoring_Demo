"""
check_config.py — config.json 을 사람이 읽을 수 있게 펼치고, 앞뒤가 맞는지 검사한다.
  uv run python hub/check_config.py        (같은 검사: plantsvc check-config / GET /api/config/check)
"""
import sys

from plantsvc.config_check import check, format_report
from plantsvc.config_store import ConfigError, ConfigStore
from plantsvc.settings import get_paths

p = get_paths()
try:
    cfg = ConfigStore(p.config, example=p.example_config).get()
except ConfigError as e:
    sys.exit(str(e))
rep = check(cfg)
print(format_report(rep))
sys.exit(0 if rep["ok"] else 1)
