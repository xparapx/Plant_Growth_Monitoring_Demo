"""
reset_run.py — 설정을 다시 잡은 시점부터 <새 구간>으로 시작한다.

  uv run python reset_run.py          보기만 함 (기본)
  uv run python reset_run.py --yes    실제로 비움

무엇을 비우고 무엇을 남기는가
  비움 : soil · pump_log · growth   — 화분 이름·ROI·배율에 묶인 값들
  남김 : readings                   — 온습도·CO2·조도. 화분 설정과 무관합니다

왜 비우는가
  ROI 를 다시 잡으면 배율이 달라지고, 화분 이름(p1·p2)이 <다른 화분>을
  가리킬 수도 있습니다. 그 상태로 과거와 이어 붙이면 생장 곡선에 계단이 생기고,
  그 계단이 처리 효과처럼 보입니다. 구간을 끊는 편이 정직합니다.

안전장치
  · plant.db 를 통째로 복사해 둡니다 (지운 뒤에도 되돌릴 수 있습니다)
  · photos/growth.jsonl 은 지우지 않고 옮깁니다 (--replay 로 옛 값이 다시 들어가지 않게)
  · photos/raw 의 사진은 손대지 않습니다 — 원본은 증거입니다
"""
import json, os, shutil, sqlite3, sys
from datetime import datetime, timezone

DB, CFG_PATH = "plant.db", "config.json"
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

try:
    rois = json.load(open(CFG_PATH)).get("rois", [])
    print("\n새 구간의 배정: " + " · ".join(f"{r['plant_id']}={r.get('treat') or '(빈칸)'}"
                                         for r in rois))
    if any(r.get("treat") not in ("stable", "fluct") for r in rois):
        print("  ★ 처리군이 비어 있습니다 — setup_camera.py 에서 먼저 배정하세요")
        sys.exit(1)
except FileNotFoundError:
    print("\n  ★ config.json 이 없습니다")
    sys.exit(1)

if not GO:
    print(f"\n  실제로 비우려면:  uv run python reset_run.py --yes")
    print(f"  (plant.db 를 먼저 복사하므로 되돌릴 수 있습니다)\n")
    sys.exit(0)

bak = f"{DB}.bak-{ts:%Y%m%d_%H%M%S}"
shutil.copy2(DB, bak)

jl = "photos/growth.jsonl"
if os.path.exists(jl):
    moved = f"photos/growth_{ts:%Y%m%d_%H%M%S}.jsonl"
    shutil.move(jl, moved)
else:
    moved = None

wiped = 0
for t in CLEAR:
    if count(t) is not None:
        wiped += conn.execute(f"DELETE FROM {t}").rowcount
conn.commit()

cfg = json.load(open(CFG_PATH))                      # 구간 시작 시각을 남깁니다
cfg["run_started"] = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}"
json.dump(cfg, open(CFG_PATH, "w"), ensure_ascii=False, indent=2)

print(f"""
  백업        {bak}
  jsonl       {moved or '(없음)'}
  비운 행     {wiped}
  구간 시작   {cfg['run_started']}  (UTC · config.json 에 기록)

  되돌리려면:  cp {bak} {DB}
  다음 촬영부터 새 구간으로 쌓입니다.
""")
