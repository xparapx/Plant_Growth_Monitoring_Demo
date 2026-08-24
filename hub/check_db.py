"""
check_db.py — DB 의 처리군 라벨이 config.json 의 배정과 맞는지 검사한다.

  uv run python check_db.py           보기만 함 (기본)
  uv run python check_db.py --fix     어긋난 행을 지움

왜 필요한가
  펌웨어를 다시 구우면 같은 화분이 <다른 처리군>으로 발행됩니다.
  예: p1 을 stable 로 굽고 돌리다가 fluct 로 바꾸면, DB 에는 두 라벨이 섞입니다.
  대시보드는 config.json 을 기준으로 묶으므로, 옛 라벨 행은
  <조용히 잘못된 군에 들어가거나> 경고만 띄우고 남습니다.

기준은 하나입니다 — <config.json 의 rois[].treat 가 정답>.
  DB 는 기록일 뿐이고, 어느 화분이 어느 군인지는 config 가 정합니다.
"""
import json, sqlite3, sys

DB, CFG_PATH = "plant.db", "config.json"
TABLES = ("soil", "pump_log", "growth")
FIX = "--fix" in sys.argv

want = {r["plant_id"]: r.get("treat", "")
        for r in json.load(open(CFG_PATH)).get("rois", [])}
if not want:
    sys.exit("config.json 에 rois 가 없습니다 — setup_camera.py 로 먼저 배치하세요")

print(f"\nconfig.json 의 배정: " + " · ".join(f"{k}={v or '(빈칸)'}" for k, v in sorted(want.items())))
print("-" * 66)

conn = sqlite3.connect(DB)
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
        for pid, tr, n, _, _ in bad:
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
    print(f"  ★ 어긋난 행 {total}개. 지우려면:  uv run python check_db.py --fix")
    print("     (지우기 전에 위 목록의 <기간>을 보고 정말 옛 기록인지 확인하세요)\n")
