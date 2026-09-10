"""frame_align — 카메라가 밀렸는지·돌아갔는지·높이가 변했는지를 <사진만으로> 알아낸다.
ArUco 마커가 하던 '위치 감시' 역할을 대신합니다.

원리
  배경(종이·책상·마운트)은 6주간 변하지 않고, 변하는 것은 <잎>뿐입니다.
  그래서 ROI(잎이 있는 곳)를 가린 뒤 기준 사진과 비교하면
  남은 어긋남이 곧 <카메라가 움직인 양>입니다.
    · 평행이동  cv2.phaseCorrelate        -> dx, dy (px)
    · 회전·배율  log-polar 변환 후 같은 방법 -> 각도(deg), 배율비

한계 — 정직하게
  · 배경이 전부 단색이면 맞출 단서가 없어 신뢰도(resp)가 떨어집니다.
  · 조명이 크게 바뀌면 값이 흔들립니다. 노출 고정이 전제입니다.
  -> resp(0~1)를 함께 돌려주고, 낮으면 <보정하지 말고 경고만> 합니다.

★ align() 은 <실패해도 예외를 던지지 않는다>는 약속으로 쓰입니다.
"""

from __future__ import annotations

import os
from typing import Any

import cv2
import numpy as np

DEF_SHIFT_WARN = 8.0
DEF_SHIFT_FAIL = 40.0
DEF_RESP_MIN = 0.05


def _prep(img, mask=None):
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
    return (F * (1 - np.exp(-(rad / (0.03 * n)) ** 2))).astype(np.float32)


def _rot_scale(ref_bgr, cur_bgr, n=512):
    """log-polar 에서 <세로 이동 = 회전>, <가로 이동 = 배율>."""
    A, B = _spectrum(_square(ref_bgr, n)), _spectrum(_square(cur_bgr, n))
    M = n / np.log(n / 2)
    fl = cv2.INTER_LINEAR + cv2.WARP_FILL_OUTLIERS
    # cv2.logPolar 은 최신 OpenCV 에서 사라졌습니다 — warpPolar(WARP_POLAR_LOG) 가 대체.
    maxr = float(np.exp(n / M))
    pflag = fl + cv2.WARP_POLAR_LOG
    a = cv2.warpPolar(A, (n, n), (n / 2, n / 2), maxr, pflag)
    b = cv2.warpPolar(B, (n, n), (n / 2, n / 2), maxr, pflag)
    win = np.outer(np.hanning(n), np.hanning(n)).astype(np.float32)
    (sx, sy), resp = cv2.phaseCorrelate(a, b, win)
    deg = -sy * 360.0 / n
    if deg > 90:
        deg -= 180
    elif deg < -90:
        deg += 180
    return float(deg), float(np.exp(-sx / M)), float(resp)


def align(cur_path, ref_path, cfg: dict[str, Any] | None = None, *, log=print) -> dict[str, Any]:
    """기준 사진 대비 현재 사진의 어긋남을 잰다.  실패해도 예외를 던지지 않습니다.

    Returns {ok, dx, dy, mag, resp, deg, scale, resp_rs, level, msg}
      level: unknown | unreliable | ok | drift | fail
    """
    cfg = cfg or {}
    qc = cfg.get("qc", {})
    out: dict[str, Any] = dict(ok=False, dx=0.0, dy=0.0, mag=0.0, resp=0.0, deg=0.0, scale=1.0,
                               resp_rs=0.0, level="unknown", msg="")

    if not ref_path or not os.path.exists(str(ref_path)):
        out["msg"] = f"기준 사진이 없습니다 ({ref_path})"
        return out
    ref = cv2.imread(str(ref_path))
    cur = cv2.imread(str(cur_path))
    if ref is None or cur is None:
        out["msg"] = f"이미지를 못 읽음 ({ref_path} / {cur_path})"
        return out
    if ref.shape != cur.shape:
        out["msg"] = f"해상도가 다름 {ref.shape[:2]} vs {cur.shape[:2]}"
        return out

    mask = _roi_mask(ref.shape, cfg.get("rois"))
    if mask.mean() < 0.15:
        out["msg"] = "배경이 15% 미만 — 맞출 단서가 부족합니다"
        return out

    try:
        a, b = _prep(ref, mask), _prep(cur, mask)
        (dx, dy), resp = cv2.phaseCorrelate(a, b)
    except Exception as e:  # noqa: BLE001 - contract: never raise
        out["msg"] = f"평행이동 검출 실패({type(e).__name__}: {e}) — 보정 없이 진행합니다"
        if log:
            log(f"[frame_align] {out['msg']}")
        return out

    try:
        deg, scale, resp2 = _rot_scale(ref, cur)
    except Exception as e:  # noqa: BLE001
        deg, scale, resp2 = 0.0, 1.0, 0.0
        if log:
            log(f"[frame_align] 회전·배율 검출 실패({type(e).__name__}: {e}) — 평행이동만 보정합니다")

    warn = float(qc.get("drift_warn_px", DEF_SHIFT_WARN))
    fail = float(qc.get("drift_fail_px", DEF_SHIFT_FAIL))
    rmin = float(qc.get("drift_resp_min", DEF_RESP_MIN))
    mag = float(np.hypot(dx, dy))

    out.update(dx=float(dx), dy=float(dy), resp=float(resp), deg=float(deg),
               scale=float(scale), mag=mag)

    if resp < rmin:
        out.update(level="unreliable",
                   msg=f"신뢰도 {resp:.3f} 낮음 — 보정하지 않습니다(배경 단서 부족·조명 변화)")
    elif mag > fail:
        out.update(level="fail",
                   msg=f"{mag:.0f}px 어긋남 — 보정 범위를 넘었습니다. 카메라를 다시 맞추고 "
                       f"calib.jpg 를 새로 찍으세요")
    elif mag > warn:
        out.update(ok=True, level="drift", msg=f"{mag:.1f}px 밀림 감지 — ROI 를 그만큼 옮겨 보정합니다")
    else:
        out.update(ok=True, level="ok", msg=f"{mag:.1f}px — 정상 범위")

    if resp2 >= rmin and abs(deg) > 1.0:
        out.update(ok=False, level="fail",
                   msg=f"회전 {deg:+.2f}도 — 평행이동 보정으로는 못 고칩니다. 카메라 각도를 다시 맞추세요")
    elif resp2 >= rmin and abs(scale - 1) > 0.015:
        out.update(ok=False, level="fail",
                   msg=f"배율 {(scale - 1) * 100:+.1f}% — 카메라 높이가 변했습니다. 다시 맞추고 calib.jpg 재촬영")
    else:
        if resp2 >= rmin and abs(deg) > 0.3:
            out["msg"] += f" · 회전 {deg:+.2f}도(경미)"
        if resp2 >= rmin and abs(scale - 1) > 0.005:
            out["msg"] += f" · 배율 {(scale - 1) * 100:+.1f}%(경미)"
    out["resp_rs"] = float(resp2)
    return out


def shift_rois(rois, dx, dy, shape=None):
    """검출된 어긋남만큼 ROI 를 옮긴 새 목록 (원본은 그대로)."""
    out = []
    for r in rois or []:
        q = dict(r)
        q["x"] = int(round(r["x"] + dx))
        q["y"] = int(round(r["y"] + dy))
        if shape is not None:
            h, w = shape[:2]
            q["x"] = max(0, min(q["x"], w - r["w"]))
            q["y"] = max(0, min(q["y"], h - r["h"]))
        out.append(q)
    return out


def _cli(argv: list[str] | None = None) -> int:
    import sys

    from ..settings import get_paths
    argv = sys.argv[1:] if argv is None else argv
    paths = get_paths()
    path = argv[0] if argv else str(paths.calib)
    ref = argv[1] if len(argv) > 1 else str(paths.calib)
    try:
        import json
        cfg = json.load(open(paths.config, encoding="utf-8"))
    except Exception:
        cfg = {}
    d = align(path, ref, cfg)
    ppc = float(cfg.get("qc", {}).get("px_per_cm_ref", 0) or 0)
    mm = f"   = {d.get('mag', 0) / ppc * 10:.2f} mm" if ppc else ""
    print(f"\n기준  {ref}\n현재  {path}\n\n  평행이동   dx {d['dx']:+7.2f} px   dy {d['dy']:+7.2f} px{mm}\n"
          f"  회전       {d['deg']:+.3f} 도\n  배율비     {d['scale']:.4f}   (1.000 이면 높이 변화 없음)\n"
          f"  신뢰도     {d['resp']:.3f}\n\n  판정  [{d['level']}]  {d['msg']}\n")
    if d["ok"] and cfg.get("rois"):
        for a, b in zip(cfg["rois"], shift_rois(cfg["rois"], d["dx"], d["dy"]), strict=False):
            if (a["x"], a["y"]) != (b["x"], b["y"]):
                print(f"  {a['plant_id']}  ({a['x']},{a['y']}) -> ({b['x']},{b['y']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
