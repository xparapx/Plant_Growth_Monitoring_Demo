import json

import cv2
import numpy as np

from plantsvc.camera.backends import FakeBackend
from plantsvc.vision import frame_align, roi_tools
from plantsvc.vision.leaf_measure import leaf_mask, measure, outline


def green_disk(w=600, h=600, r=120):
    img = np.full((h, w, 3), (140, 140, 140), np.uint8)
    cv2.circle(img, (w // 2, h // 2), r, (60, 170, 70), -1)
    return img


def test_leaf_mask_area_and_outline():
    img = green_disk()
    mask, px, blobs, _ = leaf_mask(img)
    expect = np.pi * 120 ** 2
    assert abs(px - expect) / expect < 0.03 and blobs == 1
    c = json.loads(outline(mask))
    assert len(c) == 64 and abs(np.mean([p[0] for p in c])) < 3


def test_roi_tools_grid_pack_restore_shuffle_rename():
    rois = roi_tools.grid_rois(4608, 2592, 3, 2)
    assert len(rois) == 6 and roi_tools.common_side(rois) == rois[0]["w"] and rois[0]["plant_id"] == "p1"
    boxes = [(r["x"] + 15 * (i % 2), r["y"] + 20, r["w"], r["h"]) for i, r in enumerate(rois)]  # jitter rows
    packed = roi_tools.pack_rois(boxes)
    assert [r["plant_id"] for r in packed] == ["p1", "p2", "p3", "p4", "p5", "p6"]
    assert packed[0]["x"] < packed[1]["x"] < packed[2]["x"] and packed[3]["y"] > packed[0]["y"]
    for r in rois:
        r["treat"] = "stable"
    assert roi_tools.restore_treat(rois, packed) and all(r["treat"] == "stable" for r in packed)
    moved = [dict(r, x=r["x"] + r["w"] * 2) for r in packed]          # pots swapped places -> labels dropped
    assert roi_tools.restore_treat(rois, moved) is False
    assert roi_tools.shuffle_treat(packed[:5]) is not None                 # odd count refused
    import random
    assert roi_tools.shuffle_treat(packed, random.Random(1)) is None
    assert sorted(r["treat"] for r in packed) == ["fluct"] * 3 + ["stable"] * 3
    ren = roi_tools.rename_by_order(packed, [5, 4, 3, 2, 1, 0])
    assert ren[0]["plant_id"] == "p1" and ren[0]["x"] == packed[5]["x"]
    assert roi_tools.hit_roi(packed, packed[2]["x"] + 5, packed[2]["y"] + 5) == 2
    assert roi_tools.hit_roi(packed, -1, -1) is None


def test_place_from_blobs_and_center_proposals():
    fb = FakeBackend(lambda: roi_tools.grid_rois(4608, 2592, 3, 2))
    fb.open((4608, 2592), (1280, 720))
    frame = fb.capture_array()
    blobs = roi_tools.leaf_blobs(frame)
    assert len(blobs) == 6
    rois, info = roi_tools.place_from_blobs(blobs, scale=1280 / 4608, cap_w=4608, cap_h=2592, existing=[])
    assert len(rois) == 6 and info["same"] and roi_tools.common_side(rois)
    big = fb.render(4608, 2592)
    props = roi_tools.center_proposals(big, rois)
    assert all(p["found"] for p in props) and all(abs(p["dx"]) < 80 for p in props)


def test_frame_align_detects_shift_and_never_raises(tmp_path):
    rng = np.random.default_rng(1)
    ref = rng.integers(0, 255, (400, 600, 3), dtype=np.uint8)
    ref = cv2.GaussianBlur(ref, (5, 5), 0)
    cur = np.roll(ref, (7, 12), axis=(0, 1))                        # dy=7, dx=12
    cv2.imwrite(str(tmp_path / "ref.jpg"), ref, [cv2.IMWRITE_JPEG_QUALITY, 95])
    cv2.imwrite(str(tmp_path / "cur.jpg"), cur, [cv2.IMWRITE_JPEG_QUALITY, 95])
    d = frame_align.align(str(tmp_path / "cur.jpg"), str(tmp_path / "ref.jpg"), {"qc": {}, "rois": []}, log=None)
    assert d["level"] in ("drift", "ok") and abs(abs(d["dx"]) - 12) < 2 and abs(abs(d["dy"]) - 7) < 2
    assert d["level"] == "drift" and d["ok"]
    bad = frame_align.align(str(tmp_path / "nope.jpg"), str(tmp_path / "ref.jpg"), {}, log=None)
    assert bad["ok"] is False and bad["level"] == "unknown"
    small = np.zeros((100, 100, 3), np.uint8)
    cv2.imwrite(str(tmp_path / "small.jpg"), small)
    mism = frame_align.align(str(tmp_path / "small.jpg"), str(tmp_path / "ref.jpg"), {}, log=None)
    assert "해상도" in mism["msg"]
    shifted = frame_align.shift_rois([{"plant_id": "p1", "x": 5, "y": 5, "w": 50, "h": 50}], -10, 0, (400, 600))
    assert shifted[0]["x"] == 0


def test_measure_on_fake_frame(tmp_path):
    rois = roi_tools.grid_rois(1920, 1080, 3, 2)
    fb = FakeBackend(lambda: rois)
    fb.open((1920, 1080), (1280, 720))
    fb.capture_file(str(tmp_path / "shot.jpg"))
    C = {"capture": {"size": [1920, 1080]}, "qc": {"px_per_cm_ref": 30.0}, "layout": {"pot_cm": 10}, "rois": rois}
    rows = measure(str(tmp_path / "shot.jpg"), "dawn", str(tmp_path / "dbg"), str(tmp_path / "mask"), C,
                   ref_path=None, log=None)
    assert len(rows) == 6 and all(r["ok"] for r in rows) and all(r["area_cm2"] > 0 for r in rows)
    assert (tmp_path / "dbg" / "shot_p1.jpg").exists() and (tmp_path / "mask" / "shot_p1.png").exists()
