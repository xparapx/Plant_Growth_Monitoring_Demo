"""
center_roi.py — ROI 크기는 그대로 두고 <중심만> 잎에 맞춘다.

  uv run python center_roi.py                 보기만 함 (기본)
  uv run python center_roi.py --yes           config.json 에 반영
  uv run python center_roi.py photos/raw/xxx.jpg --yes

왜 이게 필요한가
  setup_camera.py 의 미리보기(video_configuration 1280x720)와 실제 촬영
  (still_configuration 4608x2592)은 <화각이 다를 수 있다>. 미리보기에서 딱 맞게
  그린 박스가 사진에서는 밀린다. SCALE = PREV[0]/CAP_W 는 두 화각이 같다고
  전제하지만 그 전제가 항상 참은 아니다.
  그래서 이 스크립트는 <촬영한 사진 위에서> 좌표를 정한다. 미리보기를 거치지
  않으므로 화각 차이와 무관하다.

왜 크기를 안 바꾸는가
  setup_camera.py 의 [잎 찾아 배치]는 side = max(잎 가로, 잎 세로) * 1.8 로
  <잎 크기에 비례해> 박스를 만든다. 잎이 작은 화분은 작은 박스를 갖게 되고,
  그 화분이 어느 한 처리군에 속하므로 <잘림이 처리군과 정렬>된다.
  캐노피가 박스를 넘으면 작은 쪽이 먼저 잘리고, 잘린 면적과 실제로 작은 면적은
  데이터상 구분되지 않는다. 그래서 크기는 건드리지 않는다.

주의
  이걸 돌린 뒤 setup_camera.py 를 열어 [저장]하면 미리보기 기준 좌표로 덮어쓴다.
  맞춘 다음에는 열지 말 것.
"""
import argparse, glob, json, os, sys, tempfile

import cv2
import numpy as np

CFG_PATH = "config.json"

# 잎으로 인정할 최소 초록도(정규화 ExG). 중성 회색 = 0, 초록 잎 = 0.2~0.4.
# 이 문턱이 없으면 어두운 영역의 잡음 덩어리를 잎으로 착각한다 —
# leaf_mask() 의 NORM_MINMAX + Otsu 는 <무엇이 들어오든 반드시 둘로 가르기> 때문.
# 잎으로 인정할 최소 초록도(정규화 ExG). 중성 회색 = 0.
#   초록 잎은 0.25~0.45. 도트 보드·벽 같은 밝은 회색은 0.00~0.05 인데,
#   JPEG 잡음이 몇 픽셀을 0.06 위로 밀어 올리고 그게 뭉치면 잎보다 큰 덩어리가 된다.
#   실제로 선풍기·벽에 중심이 잡혔다. 0.06 은 너무 헐거웠다.
EXG_MIN  = 0.18
SEARCH   = 1.2          # ROI 를 이만큼만 넓혀 찾는다 (넓힐수록 엉뚱한 것이 들어온다)
AREA_MIN = 0.004        # 탐색창 넓이 대비 최소 크기 — 먼지·잡음 제거


def exg_of(bgr):
    """정규화 ExG. 밝기에 영향을 덜 받아 그림자에 강하다."""
    b, g, r = cv2.split(bgr.astype(np.float32))
    s = b + g + r + 1e-6
    return 2 * (g / s) - (r / s) - (b / s)


def find_leaf(img, cx, cy, w, h):
    """(cx, cy) 둘레에서 잎 덩어리를 찾아 그 무게중심을 돌려준다.
    못 찾으면 None — 억지로 아무 데나 잡지 않는다."""
    H, W = img.shape[:2]
    sw, sh = int(w * SEARCH), int(h * SEARCH)
    x0, y0 = max(0, cx - sw // 2), max(0, cy - sh // 2)
    x1, y1 = min(W, x0 + sw), min(H, y0 + sh)
    crop = img[y0:y1, x0:x1]
    if crop.size == 0:
        return None

    e = exg_of(crop)
    m = (e > EXG_MIN).astype(np.uint8) * 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    # ★ OPEN 을 먼저. 흩어진 잡음을 지운 <뒤에> 이어붙인다.
    #   순서가 반대면 잡음이 먼저 뭉쳐 커다란 가짜 덩어리가 되고, 그게 잎을 이긴다.
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k, iterations=2)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k, iterations=2)

    n, lab, st, cent = cv2.connectedComponentsWithStats(m, 8)
    if n <= 1:
        return None

    ch, cw = crop.shape[:2]
    floor = AREA_MIN * ch * cw
    ok = [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= floor]
    if not ok:
        return None
    # ★ 가장 큰 것이 아니라 <ROI 중심에 가장 가까운> 것을 고른다.
    #   화면에 다른 초록(다른 화분의 잎, 초록 물건)이 있어도 자기 화분을 지킨다.
    ccx, ccy = cw / 2, ch / 2
    i = min(ok, key=lambda j: (cent[j][0] - ccx) ** 2 + (cent[j][1] - ccy) ** 2)
    gx, gy = cent[i]
    return int(x0 + gx), int(y0 + gy), int(st[i, cv2.CC_STAT_AREA]), float(e[lab == i].mean())


def save_atomic(path, data):
    """open(path,'w') 는 여는 순간 파일을 비운다. 쓰다 죽으면 잘린 채 남는다.
    config.json 은 처리군 배정의 단일 출처라 그러면 복구가 어렵다."""
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)               # 원자적 — 옛 파일이거나 새 파일이거나


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", nargs="?", help="기본: calib.jpg, 없으면 photos/raw 의 최신")
    ap.add_argument("--yes", action="store_true", help="config.json 에 실제로 반영")
    ap.add_argument("-o", "--out", default="roi_check.jpg", help="확인용 겹친 이미지")
    a = ap.parse_args()

    src = a.image
    if not src:
        if os.path.exists("calib.jpg"):
            src = "calib.jpg"
        else:
            cand = sorted(glob.glob("photos/raw/*.jpg"))
            if not cand:
                print("사진이 없습니다. setup_camera.py 에서 [촬영] 하세요.")
                return 1
            src = cand[-1]

    img = cv2.imread(src)
    if img is None:
        print(f"못 읽음: {src}")
        return 1
    H, W = img.shape[:2]
    C = json.load(open(CFG_PATH, encoding="utf-8"))
    rois = C.get("rois", [])
    if not rois:
        print("config.json 에 rois 가 없습니다. 먼저 [격자로 나누기] 하세요.")
        return 1

    cap = tuple(C.get("capture", {}).get("size", [0, 0]))
    print(f"\n사진   {src}  {W}x{H}")
    if cap and (W, H) != cap:
        print(f"  ★ config 의 capture.size {cap[0]}x{cap[1]} 와 다릅니다 — "
              f"좌표가 안 맞을 수 있습니다")

    sizes = {(r["w"], r["h"]) for r in rois}
    print(f"ROI    {len(rois)}개 · 크기 {'모두 같음' if len(sizes) == 1 else '★ 다름 ' + str(sizes)}")
    print(f"\n{'화분':6} {'현재 중심':>14} {'잎 중심':>14} {'이동':>12}   초록도  넓이")
    print("-" * 72)

    vis = img.copy()
    moved = 0
    for r in rois:
        w, h = r["w"], r["h"]
        cx, cy = r["x"] + w // 2, r["y"] + h // 2
        hit = find_leaf(img, cx, cy, w, h)

        cv2.rectangle(vis, (r["x"], r["y"]), (r["x"] + w, r["y"] + h), (120, 120, 120), 6)

        if not hit:
            print(f"{r['plant_id']:6} {f'({cx},{cy})':>14} {'못 찾음':>14} "
                  f"{'-':>12}      —      —")
            continue

        lx, ly, area, greenness = hit
        nx = int(np.clip(lx - w // 2, 0, W - w))
        ny = int(np.clip(ly - h // 2, 0, H - h))
        dx, dy = nx - r["x"], ny - r["y"]

        print(f"{r['plant_id']:6} {f'({cx},{cy})':>14} {f'({lx},{ly})':>14} "
              f"{f'{dx:+d},{dy:+d}':>12}   {greenness:.3f}  {area:,}px")

        cv2.rectangle(vis, (nx, ny), (nx + w, ny + h), (255, 200, 0), 8)
        cv2.circle(vis, (lx, ly), 18, (0, 0, 255), -1)
        cv2.putText(vis, f"{r['plant_id']} {r.get('treat') or '(빈칸)'}",
                    (nx + 14, ny + 74), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (255, 200, 0), 5)

        if dx or dy:
            moved += 1
        r["_new"] = (nx, ny)

    cv2.imwrite(a.out, vis)
    print(f"\n확인용 이미지: {a.out}   (회색=현재 · 노랑=제안 · 빨강점=잎 중심)")

    if not a.yes:
        print("\n  실제로 반영하려면:  uv run python center_roi.py --yes\n")
        return 0

    if moved == 0:
        print("\n  이미 맞습니다. 바꿀 것 없음.\n")
        return 0

    for r in rois:
        if "_new" in r:
            r["x"], r["y"] = r.pop("_new")
    for r in rois:
        r.pop("_new", None)

    save_atomic(CFG_PATH, C)
    print(f"\n  config.json 갱신 — {moved}개 이동. 크기는 바꾸지 않았습니다.")
    print("  ★ setup_camera.py 를 열어 [저장]하면 미리보기 좌표로 덮어씁니다. 열지 마세요.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
