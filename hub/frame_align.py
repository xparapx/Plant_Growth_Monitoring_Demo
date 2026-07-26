"""
frame_align.py — 카메라가 밀렸는지·돌아갔는지·높이가 변했는지를 <사진만으로> 알아낸다.
                 ArUco 마커가 하던 '위치 감시' 역할을 대신합니다.

  라이브러리로 쓰기      import frame_align;  d = frame_align.align("photos/raw/xxx.jpg")
  단독 점검용으로 쓰기    uv run python frame_align.py photos/raw/xxx.jpg

원리
  배경(종이·책상·마운트)은 6주간 변하지 않고, 변하는 것은 <잎>뿐입니다.
  그래서 ROI(잎이 있는 곳)를 가린 뒤 기준 사진과 비교하면
  남은 어긋남이 곧 <카메라가 움직인 양>입니다.

    · 평행이동  cv2.phaseCorrelate        -> dx, dy (px)
    · 회전·배율  log-polar 변환 후 같은 방법 -> 각도(deg), 배율비

한계 — 정직하게
  · 배경이 전부 단색이면 맞출 단서가 없어 신뢰도(resp)가 떨어집니다.
  · 조명이 크게 바뀌면 값이 흔들립니다. 노출 고정이 전제입니다.
  · 잎이 프레임의 대부분을 덮으면 배경이 모자라 부정확해집니다.
  -> 그래서 resp(0~1)를 함께 돌려주고, 낮으면 <보정하지 말고 경고만> 합니다.
"""
import json, os, sys
import cv2
import numpy as np

CFG_PATH = "config.json"
REF_PATH = "calib.jpg"          # 기준 사진 = 설치 때 찍은 그 한 장

# 판정 기준 — <ROI 여유>에 비례해서 잡습니다.
#   밀림 자체는 해롭지 않습니다. ROI 창이 밀려 <잎이 잘리기 시작할 때>부터 해롭습니다.
#   그래서 고정 px 이 아니라 ROI 크기의 비율로 둡니다.
DEF_WARN_FRAC = 0.02            # ROI 한 변의 2%
DEF_FAIL_FRAC = 0.10            # ROI 한 변의 10%
DEF_SHIFT_WARN = 20.0           # px — ROI 를 모를 때의 대비값
DEF_SHIFT_FAIL = 150.0
DEF_RESP_MIN   = 0.05           # 신뢰도 하한


def _cfg():
    try:
        return json.load(open(CFG_PATH))
    except Exception:
        return {}


def _prep(img, mask=None):
    """회색조 + ROI 가리기 + 창함수.  phaseCorrelate 는 float32 를 받습니다."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    g = g.astype(np.float32)
    g -= g.mean()
    if mask is not None:
        g = g * mask
    h, w = g.shape
    win = np.outer(np.hanning(h), np.hanning(w)).astype(np.float32)
    return g * win


def _roi_mask(shape, rois, grow=1.25):
    """잎이 있는 곳을 0, 배경을 1 로. 자랄 것을 감안해 조금 넓게 가립니다."""
    h, w = shape[:2]
    m = np.ones((h, w), np.float32)
    for r in rois or []:
        cx, cy = r["x"] + r["w"] / 2, r["y"] + r["h"] / 2
        hw, hh = r["w"] * grow / 2, r["h"] * grow / 2
        x0, y0 = max(0, int(cx - hw)), max(0, int(cy - hh))
        x1, y1 = min(w, int(cx + hw)), min(h, int(cy + hh))
        m[y0:y1, x0:x1] = 0.0
    return m


def _square(img, n=512):
    """정사각형으로 줄여서 스펙트럼을 봅니다. 크기·비율이 결과에 영향을 주지 않게."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    g = cv2.resize(g.astype(np.float32), (n, n))
    g -= g.mean()
    return g * np.outer(np.hanning(n), np.hanning(n)).astype(np.float32)


def _spectrum(g):
    """FFT 진폭 스펙트럼. <평행이동에 불변>이라 회전·배율만 남습니다 (푸리에-멜린)."""
    F = np.log1p(np.fft.fftshift(np.abs(np.fft.fft2(g))))
    n = F.shape[0]
    yy, xx = np.ogrid[:n, :n]
    rad = np.hypot(yy - n / 2, xx - n / 2)
    return (F * (1 - np.exp(-(rad / (0.03 * n)) ** 2))).astype(np.float32)   # 고주파 강조


def _rot_scale(ref_bgr, cur_bgr, n=512):
    """log-polar 에서 <세로 이동 = 회전>, <가로 이동 = 배율>.
    스펙트럼은 180도 대칭이라 각도는 ±90도 범위로 접습니다."""
    A, B = _spectrum(_square(ref_bgr, n)), _spectrum(_square(cur_bgr, n))
    M = n / np.log(n / 2)
    fl = cv2.INTER_LINEAR + cv2.WARP_FILL_OUTLIERS
    a = cv2.logPolar(A, (n / 2, n / 2), M, fl)
    b = cv2.logPolar(B, (n / 2, n / 2), M, fl)
    win = np.outer(np.hanning(n), np.hanning(n)).astype(np.float32)
    (sx, sy), resp = cv2.phaseCorrelate(a, b, win)
    deg = -sy * 360.0 / n
    if deg > 90:    deg -= 180
    elif deg < -90: deg += 180
    return float(deg), float(np.exp(-sx / M)), float(resp)


def align(cur_path, ref_path=REF_PATH, cfg=None):
    """기준 사진 대비 현재 사진의 어긋남을 잰다.  실패해도 예외를 던지지 않습니다."""
    cfg = cfg or _cfg()
    qc  = cfg.get("qc", {})
    out = dict(ok=False, dx=0.0, dy=0.0, resp=0.0, deg=0.0, scale=1.0,
               level="unknown", msg="")

    ref = cv2.imread(ref_path)
    cur = cv2.imread(cur_path)
    if ref is None or cur is None:
        out["msg"] = f"이미지를 못 읽음 ({ref_path} / {cur_path})"
        return out
    if ref.shape != cur.shape:
        out["msg"] = f"해상도가 다름 {ref.shape[:2]} vs {cur.shape[:2]}"
        return out

    # ROI 를 넉넉히 가리면 배경이 모자랄 수 있습니다(화분이 프레임을 꽉 채운 경우).
    # 그때는 여유폭을 줄여 가며 배경을 확보합니다 — 포기하기 전에.
    for grow in (1.25, 1.10, 1.00):
        mask = _roi_mask(ref.shape, cfg.get("rois"), grow)
        if mask.mean() >= 0.15:
            break
    else:
        out["msg"] = (f"배경이 {mask.mean()*100:.0f}% 뿐입니다 — 맞출 단서가 부족합니다. "
                      f"ROI 를 줄이거나 카메라를 조금 높여 여백을 만드세요")
        return out
    if grow < 1.25:
        out["margin"] = grow

    a, b = _prep(ref, mask), _prep(cur, mask)
    (dx, dy), resp = cv2.phaseCorrelate(a, b)
    deg, scale, resp2 = _rot_scale(ref, cur)

    rois = cfg.get("rois") or []
    side = min([min(r["w"], r["h"]) for r in rois], default=0)
    warn = float(qc.get("drift_warn_px", side * DEF_WARN_FRAC if side else DEF_SHIFT_WARN))
    fail = float(qc.get("drift_fail_px", side * DEF_FAIL_FRAC if side else DEF_SHIFT_FAIL))
    rmin = float(qc.get("drift_resp_min", DEF_RESP_MIN))
    mag  = float(np.hypot(dx, dy))

    out.update(dx=float(dx), dy=float(dy), resp=float(resp),
               deg=float(deg), scale=float(scale), mag=mag)

    if resp < rmin:
        out.update(level="unreliable",
                   msg=f"신뢰도 {resp:.3f} 낮음 — 보정하지 않습니다(배경 단서 부족·조명 변화)")
    elif mag > fail:
        out.update(level="fail",
                   msg=f"{mag:.0f}px 어긋남 — 보정 범위를 넘었습니다. 카메라를 다시 맞추고 "
                       f"calib.jpg 를 새로 찍으세요")
    elif mag > warn:
        out.update(ok=True, level="drift",
                   msg=f"{mag:.1f}px 밀림 감지 — ROI 를 그만큼 옮겨 보정합니다")
    else:
        out.update(ok=True, level="ok",
                   msg=f"{mag:.1f}px — 정상 범위 (기준 {warn:.0f}px)")

    # 회전·배율이 변하면 ROI 를 옮기는 것만으로는 못 고칩니다 -> 재설치 판정
    if resp2 >= rmin and abs(deg) > 1.0:
        out.update(ok=False, level="fail",
                   msg=f"회전 {deg:+.2f}도 — 평행이동 보정으로는 못 고칩니다. 카메라 각도를 다시 맞추세요")
    elif resp2 >= rmin and abs(scale - 1) > 0.015:
        out.update(ok=False, level="fail",
                   msg=f"배율 {(scale-1)*100:+.1f}% — 카메라 높이가 변했습니다. 다시 맞추고 calib.jpg 재촬영")
    else:
        if resp2 >= rmin and abs(deg) > 0.3:
            out["msg"] += f" · 회전 {deg:+.2f}도(경미)"
        if resp2 >= rmin and abs(scale - 1) > 0.005:
            out["msg"] += f" · 배율 {(scale-1)*100:+.1f}%(경미)"
    out["resp_rs"] = resp2
    return out


def shift_rois(rois, dx, dy, shape=None):
    """검출된 어긋남만큼 ROI 를 옮긴 새 목록을 돌려준다 (원본은 그대로)."""
    out = []
    for r in rois or []:
        q = dict(r)
        q["x"] = int(round(r["x"] + dx))
        q["y"] = int(round(r["y"] + dy))
        if shape is not None:                       # 프레임 밖으로 나가지 않게
            h, w = shape[:2]
            q["x"] = max(0, min(q["x"], w - r["w"]))
            q["y"] = max(0, min(q["y"], h - r["h"]))
        out.append(q)
    return out


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else REF_PATH
    ref  = sys.argv[2] if len(sys.argv) > 2 else REF_PATH
    cfg  = _cfg()
    d = align(path, ref, cfg)
    ppc = float(cfg.get("qc", {}).get("px_per_cm_ref", 0) or 0)

    print(f"""
기준  {ref}
현재  {path}

  평행이동   dx {d['dx']:+7.2f} px   dy {d['dy']:+7.2f} px""" +
          (f"   = {d.get('mag',0)/ppc*10:.2f} mm" if ppc else "") + f"""
  회전       {d['deg']:+.3f} 도
  배율비     {d['scale']:.4f}   (1.000 이면 높이 변화 없음)
  신뢰도     {d['resp']:.3f}

  판정  [{d['level']}]  {d['msg']}
""")
    if d["ok"] and cfg.get("rois"):
        moved = shift_rois(cfg["rois"], d["dx"], d["dy"])
        for a, b in zip(cfg["rois"], moved):
            if (a["x"], a["y"]) != (b["x"], b["y"]):
                print(f"  {a['plant_id']}  ({a['x']},{a['y']}) -> ({b['x']},{b['y']})")
