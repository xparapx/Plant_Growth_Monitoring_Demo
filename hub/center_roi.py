"""
center_roi.py — ROI 크기는 그대로 두고 <중심만> 잎에 맞춘다.

  uv run python hub/center_roi.py                 보기만 함 (기본)
  uv run python hub/center_roi.py --yes           config.json 에 반영
  uv run python hub/center_roi.py data/photos/raw/xxx.jpg --yes

<촬영한 사진 위에서> 좌표를 정하므로 미리보기와 촬영의 화각 차이와 무관합니다.
크기를 바꾸지 않는 이유: 잎 크기에 비례한 박스는 잘림을 처리군과 정렬시킵니다.
경로는 PLANT_DATA_DIR 기준(기본 <repo>/data). 같은 기능이 웹 UI 카메라 설정의
[ROI 재중심] 버튼에도 있습니다.
"""
import argparse
import glob

import cv2

from plantsvc.config_store import ConfigStore, save_atomic  # noqa: F401
from plantsvc.settings import get_paths
from plantsvc.vision.roi_tools import (  # noqa: F401
    AREA_MIN,
    EXG_MIN,
    SEARCH,
    apply_center_proposals,
    center_proposals,
    draw_center_overlay,
    exg_of,
    find_leaf,
)

PATHS = get_paths()
CFG_PATH = str(PATHS.config)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", nargs="?", help="기본: calib.jpg, 없으면 photos/raw 의 최신")
    ap.add_argument("--yes", action="store_true", help="config.json 에 실제로 반영")
    ap.add_argument("-o", "--out", default=str(PATHS.data_dir / "roi_offset.jpg"),
                    help="확인용 — ROI 와 잎이 얼마나 어긋났는지 겹쳐 그린다")
    a = ap.parse_args()

    src = a.image
    if not src:
        if PATHS.calib.exists():
            src = str(PATHS.calib)
        else:
            cand = sorted(glob.glob(str(PATHS.raw / "*.jpg")))
            if not cand:
                print("사진이 없습니다. 웹 UI 카메라 설정에서 [촬영] 하세요.")
                return 1
            src = cand[-1]

    img = cv2.imread(src)
    if img is None:
        print(f"못 읽음: {src}")
        return 1
    H, W = img.shape[:2]
    store = ConfigStore(PATHS.config, example=PATHS.example_config)
    cfg = store.get()
    rois = [r.model_dump() for r in cfg.rois]
    if not rois:
        print("config.json 에 rois 가 없습니다. 먼저 [격자로 나누기] 하세요.")
        return 1

    cap = tuple(cfg.capture.size)
    print(f"\n사진   {src}  {W}x{H}")
    if (W, H) != cap:
        print(f"  ★ config 의 capture.size {cap[0]}x{cap[1]} 와 다릅니다 — 좌표가 안 맞을 수 있습니다")
    sizes = {(r["w"], r["h"]) for r in rois}
    print(f"ROI    {len(rois)}개 · 크기 {'모두 같음' if len(sizes) == 1 else '★ 다름 ' + str(sizes)}")
    print(f"\n{'화분':6} {'ROI 중심':>14} {'잎 무게중심':>14} {'보정량':>12}   초록도  넓이")
    print("-" * 72)

    props = center_proposals(img, rois)
    moved = 0
    for p in props:
        roi_c = f"({p['cx']},{p['cy']})"
        if not p["found"]:
            print(f"{p['plant_id']:6} {roi_c:>14} {'못 찾음':>14} {'-':>12}      —      —")
            continue
        leaf_c = f"({p['lx']},{p['ly']})"
        delta = f"{p['dx']:+d},{p['dy']:+d}"
        print(f"{p['plant_id']:6} {roi_c:>14} {leaf_c:>14} {delta:>12}   {p['greenness']:.3f}  {p['area']:,}px")
        if p["dx"] or p["dy"]:
            moved += 1

    cv2.imwrite(a.out, draw_center_overlay(img, props))
    print(f"\n확인용 이미지: {a.out}   (회색=지금 ROI · 노랑=제안 ROI · 빨강점=잎 무게중심)")

    if not a.yes:
        print("\n  실제로 반영하려면:  uv run python hub/center_roi.py --yes\n")
        return 0
    if moved == 0:
        print("\n  이미 맞습니다. 바꿀 것 없음.\n")
        return 0

    def _apply(c):
        rd = [r.model_dump() for r in c.rois]
        apply_center_proposals(rd, props)
        from plantsvc.config_model import Roi
        c.rois = [Roi(**r) for r in rd]
    store.update(_apply)
    print(f"\n  config.json 갱신 — {moved}개 이동. 크기는 바꾸지 않았습니다.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
