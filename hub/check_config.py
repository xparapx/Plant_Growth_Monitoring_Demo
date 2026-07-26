"""
check_config.py — config.json 을 사람이 읽을 수 있게 펼치고, 앞뒤가 맞는지 검사한다.
  uv run python check_config.py

  숫자를 보여주는 것보다 <서로 모순이 없는지> 잡는 것이 목적입니다.
  촬영·측정을 시작하기 전에 한 번 돌리세요.
"""
import json, sys

BAD = []          # 치명 — 고쳐야 진행 가능
WARN = []         # 주의 — 알고만 있으면 되는 것


def line(k, v, note=""):
    print(f"  {k:<22} {v}" + (f"   {note}" if note else ""))


try:
    CFG = json.load(open("config.json"))
except FileNotFoundError:
    sys.exit("config.json 이 없습니다")
except json.JSONDecodeError as e:
    sys.exit(f"config.json 문법 오류: {e}\n  ★ JSON 에는 // 주석을 쓸 수 없습니다")

CAP  = CFG.get("capture", {})
SIZE = CAP.get("size", [0, 0])
W, H = SIZE if len(SIZE) == 2 else (0, 0)
QC   = CFG.get("qc", {})
PPC  = float(QC.get("px_per_cm_ref", 0) or 0)
ROIS = CFG.get("rois", [])

# ── 촬영 조건 ────────────────────────────────────────────────
print("\n[촬영 조건]  — setup_camera / run_capture 가 공유합니다")
line("해상도", f"{W} x {H} px")
line("lens_position", CAP.get("lens_position"), "디옵터 = 1/거리(m)")
line("exposure_us", CAP.get("exposure_us"),
     f"= 1/{1e6/CAP['exposure_us']:.0f} 초" if CAP.get("exposure_us") else "")
line("gain", CAP.get("gain"))
line("colour_gains", CAP.get("colour_gains"), "(적색, 청색)")

g = float(CAP.get("gain", 0) or 0)
if g > 4:
    WARN.append(f"gain {g} — 조명이 어둡습니다. 노이즈가 ExG 분리를 방해합니다")
if not CAP.get("lens_position"):
    BAD.append("lens_position 이 비어 있습니다 — [자동 측정] 후 [저장] 하세요")

# ── 배율 ─────────────────────────────────────────────────────
print("\n[배율]")
if PPC > 0:
    line("px_per_cm_ref", f"{PPC:.1f} px/cm")
    line("프레임 실제 크기", f"{W/PPC:.1f} x {H/PPC:.1f} cm")
    line("1 px", f"{10/PPC:.2f} mm")
else:
    line("px_per_cm_ref", "없음")
    BAD.append("px_per_cm_ref 가 0 입니다 — 마커가 없으면 area_cm2 가 null 이 되고\n"
               "        측정 행이 ok=0 으로 기록되어 대시보드가 전부 걸러냅니다")

if CFG.get("ref_marker"):
    line("ref_marker", "있음", "카메라가 밀려도 ROI 자동 정렬됨")
else:
    line("ref_marker", "없음", "위치 보정 없음 — 카메라를 6주간 절대 건드리지 마세요")

# ── ROI ──────────────────────────────────────────────────────
print(f"\n[ROI]  {len(ROIS)} 칸")
if not ROIS:
    BAD.append("rois 가 비어 있습니다 — [잎 찾아 배치] 를 누르세요")

counts = {}
for r in ROIS:
    t = r.get("treat") or "(빈칸)"
    counts[t] = counts.get(t, 0) + 1
    x, y, w, h = r.get("x", 0), r.get("y", 0), r.get("w", 0), r.get("h", 0)
    cm = f"{w/PPC:.1f} x {h/PPC:.1f} cm" if PPC > 0 else ""
    flag = ""
    if x < 0 or y < 0 or x + w > W or y + h > H:
        flag = "  ← 화면 밖!"
        BAD.append(f'{r.get("plant_id")} 의 ROI 가 프레임을 벗어납니다')
    line(f'{r.get("plant_id")}  [{t}]', f"({x},{y}) {w}x{h} px  {cm}", flag)

    if t not in ("stable", "fluct"):
        BAD.append(f'{r.get("plant_id")} 의 treat 가 "{t}" 입니다 — '
                   'stable / fluct 만 대시보드가 인식합니다')

# ROI 겹침
for i in range(len(ROIS)):
    for j in range(i + 1, len(ROIS)):
        a, b = ROIS[i], ROIS[j]
        ox = min(a["x"]+a["w"], b["x"]+b["w"]) - max(a["x"], b["x"])
        oy = min(a["y"]+a["h"], b["y"]+b["h"]) - max(a["y"], b["y"])
        if ox > 0 and oy > 0:
            BAD.append(f'{a["plant_id"]} 와 {b["plant_id"]} 의 ROI 가 겹칩니다 '
                       f'({ox}x{oy} px) — 잎이 두 번 세어집니다')

print("\n[처리군]")
for t, n in sorted(counts.items()):
    line(t, f"{n} 칸")
if len(counts) == 2 and len(set(counts.values())) > 1:
    WARN.append("두 처리군의 화분 수가 다릅니다 — 비교의 검정력이 떨어집니다")
if len(ROIS) and len(counts) == 1:
    WARN.append("처리군이 한 종류뿐입니다 — [처리군 무작위 배정] 을 누르세요")

# ── 배율 정합성: 프레임이 배치를 담을 수 있는가 ─────────────
LAY0 = CFG.get("layout", {})
if PPC > 0 and LAY0:
    cols = int(LAY0.get("cols", 1)); rows = int(LAY0.get("rows", 1))
    pot  = float(LAY0.get("pot_cm", 0) or 0)
    gap  = float(LAY0.get("gap_cm", 0) or 0)
    need_w = cols * pot + (cols - 1) * gap
    frame_w = W / PPC
    print("\n[정합성]")
    line("프레임 폭", f"{frame_w:.1f} cm", "= 해상도 / 배율")
    line("배치가 차지하는 폭", f"{need_w:.1f} cm", f"({cols}열 · 화분 {pot:.0f} · 틈 {gap:.0f})")
    if need_w > frame_w:
        BAD.append(f"화분 배치({need_w:.0f}cm)가 프레임({frame_w:.0f}cm)보다 넓습니다 — "
                   "배율이나 layout 중 하나가 틀렸습니다.\n"
                   "        두 점 클릭 때 <실제 길이> 입력칸과 실제로 찍은 두 점이 같은 대상인지 확인하세요")
    elif need_w > 0 and frame_w > need_w * 3:
        WARN.append(f"프레임({frame_w:.0f}cm)이 배치({need_w:.0f}cm)의 3배가 넘습니다 — "
                    "배경만 넓게 찍혀 배율이 낭비됩니다")

# ── 화분 크기 대비 ROI 여유 ─────────────────────────────────
LAY = CFG.get("layout", {})
pot = float(LAY.get("pot_cm", 0) or 0)
if PPC > 0 and pot > 0 and ROIS:
    side_cm = min(min(r["w"], r["h"]) for r in ROIS) / PPC
    print("\n[여유]")
    line("화분 지름", f"{pot:.0f} cm")
    line("가장 작은 ROI 한 변", f"{side_cm:.1f} cm", f"= 화분의 {side_cm/pot:.1f} 배")
    if side_cm < pot * 1.5:
        WARN.append(f"ROI 가 화분 지름의 {side_cm/pot:.1f} 배뿐입니다 — "
                    "6주 뒤 잎이 박스 밖으로 나가면 그때부터 면적이 잘립니다 (1.5~2 배 권장)")

# ── 결과 ─────────────────────────────────────────────────────
print()
for w in WARN:
    print(f"  주의  {w}")
for b in BAD:
    print(f"  문제  {b}")
if not BAD:
    print("  ✔ 치명적인 문제 없음 — 촬영·측정을 시작해도 됩니다")
print()
