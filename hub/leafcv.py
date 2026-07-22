"""
leafcv -- PROJECTED CANOPY AREA from a top-view image.

NOTE ON NAMING
  This is NOT leaf area.  Overlapping leaves are counted once, so it always
  under-reads true leaf area.  It is a monotonic growth proxy -- enough for
  growth-RATE comparison, but report it as projected canopy area.
"""
import json
import cv2
import numpy as np

CFG = json.load(open("config.json"))

def find_scale(img):
    """px per cm from the ArUco marker, or None."""
    d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    det = cv2.aruco.ArucoDetector(d, cv2.aruco.DetectorParameters())
    corners, ids, _ = det.detectMarkers(img)
    if ids is None or len(corners) == 0:
        return None
    c = corners[0].reshape(4, 2)
    sides = [np.linalg.norm(c[i] - c[(i + 1) % 4]) for i in range(4)]
    return (float(np.mean(sides)) / CFG["marker_mm"]) * 10.0

def leaf_mask(bgr):
    b, g, r = cv2.split(bgr.astype(np.float32))
    exg = 2.0 * g - r - b                       # excess green index
    exg = cv2.normalize(exg, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    exg = cv2.GaussianBlur(exg, (5, 5), 0)
    _, m = cv2.threshold(exg, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN,  k, iterations=1)   # drop specks
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k, iterations=2)   # fill holes

    # keep only the largest blob = the plant.  kills stray green pixels.
    nlab, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    if nlab <= 1:
        return np.zeros_like(m), 0
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return np.where(lab == big, 255, 0).astype(np.uint8), int(stats[big, cv2.CC_STAT_AREA])

def measure(img_path, debug_dir=None):
    img = cv2.imread(img_path)
    if img is None:
        raise FileNotFoundError(img_path)
    ppc = find_scale(img)
    if ppc is None:
        print("[WARN] ArUco not found -- area_cm2 will be null")

    out = []
    for roi in CFG["rois"]:
        x, y, w, h = roi["x"], roi["y"], roi["w"], roi["h"]
        crop = img[y:y + h, x:x + w]
        mask, px = leaf_mask(crop)
        cm2 = round(px / (ppc ** 2), 2) if ppc else None
        ok = 1 if (ppc and 0 < px < 0.9 * w * h) else 0   # blob filling ROI = bad crop
        out.append({"plant_id": roi["plant_id"], "treat": roi["treat"],
                    "area_px": px, "area_cm2": cm2,
                    "px_per_cm": round(ppc, 3) if ppc else None, "ok": ok})
        if debug_dir:
            vis = crop.copy()
            cont, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(vis, cont, -1, (0, 0, 255), 3)
            cv2.putText(vis, f'{roi["plant_id"]} {cm2}cm2', (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
            cv2.imwrite(f'{debug_dir}/{roi["plant_id"]}.jpg', vis)
    return out

if __name__ == "__main__":
    import sys, os
    os.makedirs("debug", exist_ok=True)
    for r in measure(sys.argv[1] if len(sys.argv) > 1 else "calib.jpg", "debug"):
        print(r)
