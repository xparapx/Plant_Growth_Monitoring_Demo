"""
check_db.py — DB 의 처리군 라벨이 config.json 의 배정과 맞는지 검사한다.

  uv run python hub/check_db.py           보기만 함 (기본)
  uv run python hub/check_db.py --fix     어긋난 행을 지움  (plant.db 를 쓰는 유일한 예외 — CLI 전용)

기준은 하나입니다 — <config.json 의 rois[].treat 가 정답>.
"""
import sqlite3
import sys

from plantsvc.config_store import ConfigStore
from plantsvc.settings import get_paths

p = get_paths()
TABLES = ("soil", "pump_log", "growth")
FIX = "--fix" in sys.argv

want = ConfigStore(p.config, example=p.example_config).get().roi_map()
if not want:
    sys.exit("config.json 에 rois 가 없습니다 — 웹 UI 카메라 설정에서 먼저 배치하세요")

print("\nconfig.json 의 배정: " + " · ".join(f"{k}={v or '(빈칸)'}" for k, v in sorted(want.items())))
print("-" * 66)

conn = sqlite3.connect(p.db)
total = 0
for t in TABLES:
    try:
        rows = list(conn.execute(
            f"SELECT plant_id, treat, COUNT(*), MIN(ts), MAX(ts) "
            f"FROM {t} GROUP BY plant_id, treat ORDER BY plant_id, treat"))
    except sqlite3.OperationalError:
        continue
    bad = [r for r in rows if want.get(r[0], "\0") != (r[1] or "")]
    print(f"\n[{t}]")
    for pid, tr, n, lo, hi in rows:
        ok = want.get(pid, "\0") == (tr or "")
        mark = "   " if ok else " ★ "
        print(f" {mark}{pid or '(없음)':6} {tr or '(빈칸)':8} {n:6}행  {lo}  ~  {hi}"
              + ("" if ok else f"   -> config 는 '{want.get(pid, '해당 화분 없음')}'"))
    total += sum(r[2] for r in bad)

    if bad and FIX:
        for pid, tr, _n, _, _ in bad:
            if tr is None:
                conn.execute(f"DELETE FROM {t} WHERE plant_id IS ? AND treat IS NULL", (pid,))
            else:
                conn.execute(f"DELETE FROM {t} WHERE plant_id IS ? AND treat = ?", (pid, tr))
        conn.commit()

print("-" * 66)
if total == 0:
    print("  ✔ 모든 라벨이 config.json 과 일치합니다\n")
elif FIX:
    print(f"  {total}행을 지웠습니다. 대시보드를 새로고침하세요.\n")
else:
    print(f"  ★ 어긋난 행 {total}개. 지우려면:  uv run python hub/check_db.py --fix")
    print("     (지우기 전에 위 목록의 <기간>을 보고 정말 옛 기록인지 확인하세요)\n")
