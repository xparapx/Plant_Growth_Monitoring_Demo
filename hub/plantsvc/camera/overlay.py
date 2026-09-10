"""Burned-in preview overlay (setup_camera.draw) - optional; the React UI draws its own SVG."""

from __future__ import annotations

import cv2


def draw(img, rois, scale: float, pts, ppc: float | None):
    h, w = img.shape[:2]
    m = int(min(w, h) * 0.05)
    cv2.rectangle(img, (m, m), (w - m, h - m), (150, 150, 150), 1)
    for r in rois or []:
        x, y = int(r["x"] * scale), int(r["y"] * scale)
        ww, hh = int(r["w"] * scale), int(r["h"] * scale)
        out = x < 0 or y < 0 or x + ww > w or y + hh > h
        col = (0, 0, 255) if out else (255, 170, 0)
        cv2.rectangle(img, (x, y), (x + ww, y + hh), col, 2)
        cv2.putText(img, f'{r["plant_id"]} {r.get("treat") or "?"}', (x + 6, y + 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
        if out:
            cv2.putText(img, "OUT OF FRAME", (x + 6, y + 48), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
    for px, py in pts or []:
        cv2.circle(img, (int(px), int(py)), 7, (0, 255, 255), -1)
    if pts and len(pts) == 2:
        a, b = [(int(p[0]), int(p[1])) for p in pts]
        cv2.line(img, a, b, (0, 255, 255), 2)
    cv2.rectangle(img, (0, h - 34), (w, h), (0, 0, 0), -1)
    txt = f"{ppc:.1f} px/cm" if ppc else "px/cm --"
    cv2.putText(img, f"{txt}    ROI {len(rois or [])}", (10, h - 11), cv2.FONT_HERSHEY_SIMPLEX, 0.62,
                (255, 255, 255), 2)
    return img
