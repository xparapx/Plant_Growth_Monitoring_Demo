"""ROI placement helpers - pure functions on the config `rois` list.

Ported from setup_camera.py (`_pack`, `_common_side`, `_restore_treat`, the
blob search of `act_findleaf`, `act_autoroi`, `act_pickroi`) and center_roi.py
(`exg_of`, `find_leaf`).  No camera, no HTTP, no globals - so the rules that
protect the experiment can be unit-tested:

  * all ROIs share one square side (a size that follows leaf size would align
    clipping with the treatment group - a silent confound);
  * rows are grouped by box height, not fixed bands (a slightly offset pot must
    not flip p1/p2 and silently repoint historical data);
  * treatment labels survive a re-placement only if every new centre still
    falls inside its old box.
"""

from __future__ import annotations

import random
from typing import Any

import cv2
import numpy as np

# ---- centre-on-leaf (center_roi.py) ------------------------------------------
EXG_MIN = 0.18       # 잎으로 인정할 최소 초록도(정규화 ExG). 중성 회색 = 0, 잎 = 0.25~0.45
SEARCH = 1.2         # ROI 를 이만큼만 넓혀 찾는다
AREA_MIN = 0.004     # 탐색창 넓이 대비 최소 크기 — 먼지·잡음 제거


def exg_of(bgr):
    """정규화 ExG. 밝기에 영향을 덜 받아 그림자에 강하다."""
    b, g, r = cv2.split(bgr.astype(np.float32))
    s = b + g + r + 1e-6
    return 2 * (g / s) - (r / s) - (b / s)


def find_leaf(img, cx, cy, w, h):
    """(cx, cy) 둘레에서 잎 덩어리를 찾아 그 <면적 무게중심>을 돌려준다.  못 찾으면 None."""
    H, W = img.shape[:2]
    sw, sh = int(w * SEARCH), int(h * SEARCH)
    x0, y0 = max(0, int(cx) - sw // 2), max(0, int(cy) - sh // 2)
    x1, y1 = min(W, x0 + sw), min(H, y0 + sh)
    crop = img[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    e = exg_of(crop)
    m = (e > EXG_MIN).astype(np.uint8) * 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k, iterations=2)     # ★ OPEN 먼저
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k, iterations=2)
    n, lab, st, cent = cv2.connectedComponentsWithStats(m, 8)
    if n <= 1:
        return None
    ch, cw = crop.shape[:2]
    floor = AREA_MIN * ch * cw
    ok = [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= floor]
    if not ok:
        return None
    ccx, ccy = cw / 2, ch / 2           # ★ 가장 큰 것이 아니라 ROI 중심에 가장 가까운 것
    i = min(ok, key=lambda j: (cent[j][0] - ccx) ** 2 + (cent[j][1] - ccy) ** 2)
    gx, gy = cent[i]
    return int(x0 + gx), int(y0 + gy), int(st[i, cv2.CC_STAT_AREA]), float(e[lab == i].mean())


def center_proposals(img, rois: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """For each ROI: where the leaf centroid is and where the box would move (size unchanged)."""
    H, W = img.shape[:2]
    out = []
    for r in rois:
        w, h = int(r["w"]), int(r["h"])
        cx, cy = int(r["x"]) + w // 2, int(r["y"]) + h // 2
        hit = find_leaf(img, cx, cy, w, h)
        row = {"plant_id": r["plant_id"], "treat": r.get("treat", ""), "x": int(r["x"]),
               "y": int(r["y"]), "w": w, "h": h, "cx": cx, "cy": cy, "found": bool(hit)}
        if hit:
            lx, ly, area, greenness = hit
            nx = int(np.clip(lx - w // 2, 0, W - w))
            ny = int(np.clip(ly - h // 2, 0, H - h))
            row.update(lx=lx, ly=ly, area=area, greenness=round(greenness, 3),
                       nx=nx, ny=ny, dx=nx - int(r["x"]), dy=ny - int(r["y"]))
        out.append(row)
    return out


def draw_center_overlay(img, proposals: list[dict[str, Any]]):
    vis = img.copy()
    for p in proposals:
        cv2.rectangle(vis, (p["x"], p["y"]), (p["x"] + p["w"], p["y"] + p["h"]), (120, 120, 120), 6)
        if not p["found"]:
            continue
        nx, ny, w, h = p["nx"], p["ny"], p["w"], p["h"]
        cv2.rectangle(vis, (nx, ny), (nx + w, ny + h), (255, 200, 0), 8)
        cv2.circle(vis, (p["lx"], p["ly"]), 18, (0, 0, 255), -1)
        cv2.putText(vis, f"{p['plant_id']} {p.get('treat') or '(none)'}", (nx + 14, ny + 74),
                    cv2.FONT_HERSHEY_SIMPLEX, 2.0, (255, 200, 0), 5)
    return vis


def apply_center_proposals(rois: list[dict[str, Any]], proposals: list[dict[str, Any]]) -> int:
    """Move rois in place to the proposed positions.  Returns the number moved."""
    by_id = {p["plant_id"]: p for p in proposals if p["found"]}
    moved = 0
    for r in rois:
        p = by_id.get(r["plant_id"])
        if p and (p["dx"] or p["dy"]):
            r["x"], r["y"] = p["nx"], p["ny"]
            moved += 1
    return moved


# ---- preview-frame leaf blobs (setup_camera act_findleaf) ----------------------
def leaf_blobs(frame_bgr, *, min_area_frac=0.005, min_exg=0.06) -> list[dict[str, Any]]:
    """ExG -> Otsu -> morphology -> connected components; keep blobs that are big AND green.
    Returns [{cx, cy, w, h, area}] in the frame's own pixel coordinates."""
    b, g, r = cv2.split(frame_bgr.astype(np.float32))
    ssum = b + g + r + 1e-6
    exg = 2 * (g / ssum) - (r / ssum) - (b / ssum)
    x8 = cv2.normalize(exg, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    x8 = cv2.GaussianBlur(x8, (7, 7), 0)
    _, m = cv2.threshold(x8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k, iterations=2)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k, iterations=1)
    n, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
    ph, pw = m.shape
    out = []
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] > min_area_frac * pw * ph and float(exg[lab == i].mean()) > min_exg:
            out.append({"cx": float(cen[i][0]), "cy": float(cen[i][1]),
                        "w": int(st[i, cv2.CC_STAT_WIDTH]), "h": int(st[i, cv2.CC_STAT_HEIGHT]),
                        "area": int(st[i, cv2.CC_STAT_AREA])})
    return out


def common_side(rois: list[dict[str, Any]]) -> int | None:
    """If every ROI is the same square, that side; else None."""
    if not rois:
        return None
    sides = {(int(r["w"]), int(r["h"])) for r in rois}
    if len(sides) != 1:
        return None
    w, h = sides.pop()
    return w if w == h else None


def pack_rois(boxes: list[tuple[float, float, float, float]]) -> list[dict[str, Any]]:
    """Sort boxes into rows (by box-height median, not fixed bands), then left->right; name p1..pN."""
    if not boxes:
        return []
    hh = sorted(b[3] for b in boxes)[len(boxes) // 2]
    tol = hh * 0.5
    rows: list[list] = []
    cur: list = []
    for b in sorted(boxes, key=lambda b: b[1] + b[3] / 2):
        if cur and (b[1] + b[3] / 2) - (cur[-1][1] + cur[-1][3] / 2) > tol:
            rows.append(cur)
            cur = []
        cur.append(b)
    rows.append(cur)
    ordered = [b for r in rows for b in sorted(r, key=lambda b: b[0])]
    return [{"plant_id": f"p{i}", "treat": "", "x": int(x), "y": int(y), "w": int(w), "h": int(h)}
            for i, (x, y, w, h) in enumerate(ordered, 1)]


def restore_treat(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> bool:
    """Carry treatment labels over a re-placement only if the pots did not swap places."""
    if len(before) != len(after) or not before:
        return False
    for old, new in zip(before, after, strict=True):
        cx, cy = new["x"] + new["w"] / 2, new["y"] + new["h"] / 2
        if not (old["x"] <= cx <= old["x"] + old["w"] and old["y"] <= cy <= old["y"] + old["h"]):
            return False
    for old, new in zip(before, after, strict=True):
        new["treat"] = old.get("treat", "")
    return True


def place_from_blobs(blobs: list[dict[str, Any]], *, scale: float, cap_w: int, cap_h: int,
                     existing: list[dict[str, Any]], expand: float = 1.8) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """act_findleaf placement: move centres only; one common square side; shrink together on overlap.
    `blobs` are in preview px, `scale` = preview/capture."""
    keep = common_side(existing)
    if keep:
        side = keep * scale
        how = f"기존 크기 {keep}px 유지"
    else:
        side = max(max(b["w"], b["h"]) for b in blobs) * expand
        how = "새 크기(가장 큰 잎 기준) · 전부 동일"

    def mk(s):
        return [[b["cx"] - s / 2, b["cy"] - s / 2, s, s] for b in blobs]

    boxes = mk(side)
    shrunk = False
    for _ in range(12):
        over = any(
            min(a[0] + a[2], c[0] + c[2]) - max(a[0], c[0]) > 0 and
            min(a[1] + a[3], c[1] + c[3]) - max(a[1], c[1]) > 0
            for i, a in enumerate(boxes) for c in boxes[i + 1:])
        if not over:
            break
        side *= 0.90
        boxes = mk(side)
        shrunk = True
    if shrunk:
        how += " (겹쳐서 축소)"

    out = []
    for x, y, w, h in boxes:
        X, Y, W_, H_ = x / scale, y / scale, w / scale, h / scale
        W_ = min(W_, cap_w)
        H_ = min(H_, cap_h)
        X = max(0, min(X, cap_w - W_))
        Y = max(0, min(Y, cap_h - H_))
        out.append((X, Y, W_, H_))

    before = [dict(r) for r in existing]
    rois = pack_rois(out)
    kept = restore_treat(before, rois)
    sides = {r["w"] for r in rois}
    return rois, {"how": how, "kept": kept, "n": len(out), "same": len(sides) == 1}


def grid_rois(cap_w: int, cap_h: int, cols: int, rows: int, margin: float = 0.04) -> list[dict[str, Any]]:
    """Even cols x rows grid of equal squares; treat left empty on purpose."""
    cols, rows = max(1, int(cols)), max(1, int(rows))
    mx, my = int(cap_w * margin), int(cap_h * margin)
    cw = (cap_w - 2 * mx) // cols
    ch = (cap_h - 2 * my) // rows
    side = int(min(cw, ch) * 0.92)
    out, n = [], 1
    for r in range(rows):
        for c in range(cols):
            cx = mx + cw * c + cw // 2
            cy = my + ch * r + ch // 2
            out.append({"plant_id": f"p{n}", "treat": "",
                        "x": cx - side // 2, "y": cy - side // 2, "w": side, "h": side})
            n += 1
    return out


def hit_roi(rois: list[dict[str, Any]], X: float, Y: float) -> int | None:
    for i, r in enumerate(rois):
        if r["x"] <= X <= r["x"] + r["w"] and r["y"] <= Y <= r["y"] + r["h"]:
            return i
    return None


def rename_by_order(rois: list[dict[str, Any]], order: list[int]) -> list[dict[str, Any]]:
    """Rename p1..pN in the clicked order (treatment follows the box)."""
    return [dict(rois[i], plant_id=f"p{k}") for k, i in enumerate(order, 1)]


def shuffle_treat(rois: list[dict[str, Any]], rng: random.Random | None = None) -> str | None:
    """Assign half stable / half fluct at random, in place.  Returns an error message or None."""
    n = len(rois)
    if n == 0:
        return "ROI 가 없습니다"
    if n % 2:
        return f"ROI 가 {n}개(홀수)라 반씩 나눌 수 없습니다"
    labels = ["stable"] * (n // 2) + ["fluct"] * (n // 2)
    (rng or random).shuffle(labels)
    for r, t in zip(rois, labels, strict=True):
        r["treat"] = t
    return None
