"""
reset_run.py — 설정을 다시 잡은 시점부터 <새 구간>으로 시작한다.

  uv run python hub/reset_run.py          보기만 함 (기본)
  uv run python hub/reset_run.py --yes    실제로 비움

비움 : soil · pump_log · growth   /  남김 : readings
안전장치: plant.db 통째 백업, growth.jsonl 은 옮김(--replay 재유입 방지), photos/raw 는 손대지 않음.
"""
import shutil
import sqlite3
import sys
from datetime import datetime, timezone

from plantsvc.config_store import ConfigStore
from plantsvc.settings import get_paths

p = get_paths()
DB = p.db
CLEAR, KEEP = ("soil", "pump_log", "growth"), ("readings",)
GO = "--yes" in sys.argv
ts = datetime.now()

conn = sqlite3.connect(DB)


def count(t):
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    except sqlite3.OperationalError:
        return None


print(f"\n{'표':12} {'행':>8}   처리")
print("-" * 46)
for t in CLEAR:
    n = count(t)
    print(f"  {t:10} {n if n is not None else '-':>8}   비움")
for t in KEEP:
    n = count(t)
    print(f"  {t:10} {n if n is not None else '-':>8}   그대로 둠")

store = ConfigStore(p.config, example=p.example_config)
cfg = store.get()
print("\n새 구간의 배정: " + " · ".join(f"{r.plant_id}={r.treat or '(빈칸)'}" for r in cfg.rois))
if not cfg.rois or any(r.treat not in ("stable", "fluct") for r in cfg.rois):
    print("  ★ 처리군이 비어 있습니다 — 웹 UI 카메라 설정에서 먼저 배정하세요")
    sys.exit(1)

if not GO:
    print("\n  실제로 비우려면:  uv run python hub/reset_run.py --yes")
    print("  (plant.db 를 먼저 복사하므로 되돌릴 수 있습니다)\n")
    sys.exit(0)

bak = f"{DB}.bak-{ts:%Y%m%d_%H%M%S}"
shutil.copy2(DB, bak)

moved = None
if p.jsonl.exists():
    moved = p.photos / f"growth_{ts:%Y%m%d_%H%M%S}.jsonl"
    shutil.move(str(p.jsonl), str(moved))

wiped = 0
for t in CLEAR:
    if count(t) is not None:
        wiped += conn.execute(f"DELETE FROM {t}").rowcount
conn.commit()

started = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}"


def _mark(c):
    c.run_started = started


store.update(_mark)

print(f"""
  백업        {bak}
  jsonl       {moved or '(없음)'}
  비운 행     {wiped}
  구간 시작   {started}  (UTC · config.json 에 기록)

  되돌리려면:  cp {bak} {DB}
  다음 촬영부터 새 구간으로 쌓입니다.
""")
