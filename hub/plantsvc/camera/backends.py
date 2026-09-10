"""Camera backends.

Picamera2Backend keeps the invariant from setup_camera.py: ONE
create_still_configuration(main=capture.size, lores=preview.size) so the
preview and the still share the same field of view and SCALE = prev_w/cap_w
is a pure proportion.  FakeBackend renders a grey tray with green blobs where
the config ROIs are, so the whole setup flow and the capture routine run on a
PC, in CI, and on a Pi without a camera.
"""

from __future__ import annotations

import math
import os
import time
from typing import Any, Protocol

import cv2
import numpy as np


class CameraUnavailable(RuntimeError):
    pass


class CameraBackend(Protocol):
    kind: str

    def open(self, main: tuple[int, int], lores: tuple[int, int]) -> str: ...
    def close(self) -> None: ...
    def apply_manual(self, capture: dict[str, Any]) -> None: ...
    def enable_auto(self) -> None: ...
    def autofocus_cycle(self) -> None: ...
    def capture_metadata(self) -> dict[str, Any]: ...
    def capture_array(self) -> np.ndarray: ...
    def capture_file(self, path: str) -> None: ...


class Picamera2Backend:
    kind = "picamera2"

    def __init__(self, acquire_tries: int = 3, acquire_wait: float = 30.0, log=print):
        self.cam = None
        self.prev_stream = "lores"
        self.acquire_tries, self.acquire_wait = acquire_tries, acquire_wait
        self.log = log

    def open(self, main, lores) -> str:
        from picamera2 import Picamera2
        cam = None
        for i in range(self.acquire_tries):
            try:
                cam = Picamera2()
                break
            except RuntimeError as e:
                if i == self.acquire_tries - 1:
                    raise CameraUnavailable(
                        f"카메라를 못 잡았습니다 ({e}). 다른 프로세스가 쥐고 있는지 확인: "
                        f"pgrep -af setup_camera.py ; sudo fuser -v /dev/media0") from e
                self.log(f"[RETRY] 카메라 사용 중 — {self.acquire_wait:.0f}초 뒤 재시도 ({i + 1}/{self.acquire_tries})")
                time.sleep(self.acquire_wait)
        assert cam is not None
        try:
            cfg = cam.create_still_configuration(main={"size": tuple(main)},
                                                 lores={"size": tuple(lores), "format": "RGB888"},
                                                 buffer_count=2)
            cam.configure(cfg)
            self.prev_stream = "lores"
        except Exception as e:  # noqa: BLE001 - old picamera2 only allows YUV420 lores
            self.log(f"[INFO] RGB888 lores 실패 ({e}) — YUV420 으로 재시도")
            cfg = cam.create_still_configuration(main={"size": tuple(main)},
                                                 lores={"size": tuple(lores), "format": "YUV420"},
                                                 buffer_count=2)
            cam.configure(cfg)
            self.prev_stream = "lores_yuv"
        cam.start()
        self.cam = cam
        return self.prev_stream

    def close(self) -> None:
        cam, self.cam = self.cam, None
        if cam is not None:
            try:
                cam.stop()
            except Exception:
                pass
            try:
                cam.close()
            except Exception:
                pass

    def _controls(self):
        from libcamera import controls
        return controls

    def apply_manual(self, capture: dict[str, Any]) -> None:
        c = self._controls()
        self.cam.set_controls({
            "AfMode": c.AfModeEnum.Manual, "LensPosition": float(capture["lens_position"]),
            "AeEnable": False, "ExposureTime": int(capture["exposure_us"]),
            "AnalogueGain": float(capture["gain"]),
            "AwbEnable": False, "ColourGains": tuple(float(x) for x in capture["colour_gains"]),
        })

    def enable_auto(self) -> None:
        c = self._controls()
        self.cam.set_controls({"AeEnable": True, "AwbEnable": True, "AfMode": c.AfModeEnum.Auto})

    def autofocus_cycle(self) -> None:
        try:
            self.cam.autofocus_cycle()
        except Exception:
            pass

    def capture_metadata(self) -> dict[str, Any]:
        m = self.cam.capture_metadata()
        return {"ExposureTime": m.get("ExposureTime"), "AnalogueGain": m.get("AnalogueGain"),
                "ColourGains": m.get("ColourGains"), "LensPosition": m.get("LensPosition")}

    def capture_array(self) -> np.ndarray:
        a = self.cam.capture_array("lores")
        if self.prev_stream == "lores_yuv":
            a = cv2.cvtColor(a, cv2.COLOR_YUV420p2BGR)
        return a

    def capture_file(self, path: str) -> None:
        self.cam.capture_file(str(path), name="main")


class FakeBackend:
    """Synthetic tray: grey board, 1 cm-ish dot grid, one green blob per config ROI (or 3x2)."""
    kind = "fake"

    def __init__(self, rois_getter=None, seed: int = 3, log=print):
        self.rois_getter = rois_getter
        self.seed = seed
        self.main = (4608, 2592)
        self.lores = (1280, 720)
        self.controls: dict[str, Any] = {"ExposureTime": 20000, "AnalogueGain": 2.0,
                                         "ColourGains": (1.8, 1.6), "LensPosition": 1.82}
        self.auto = False
        self.opened = False
        self.log = log

    def open(self, main, lores) -> str:
        self.main, self.lores = tuple(main), tuple(lores)
        self.opened = True
        return "lores"

    def close(self) -> None:
        self.opened = False

    def apply_manual(self, capture: dict[str, Any]) -> None:
        self.auto = False
        self.controls.update(ExposureTime=int(capture["exposure_us"]), AnalogueGain=float(capture["gain"]),
                             ColourGains=tuple(capture["colour_gains"]), LensPosition=float(capture["lens_position"]))

    def enable_auto(self) -> None:
        self.auto = True
        self.controls.update(ExposureTime=18000, AnalogueGain=1.6, ColourGains=(1.9, 1.5), LensPosition=1.9)

    def autofocus_cycle(self) -> None:
        return None

    def capture_metadata(self) -> dict[str, Any]:
        return dict(self.controls)

    # ---- rendering ---------------------------------------------------------------
    def _blob_centres(self, w: int, h: int) -> list[tuple[float, float, float]]:
        rois = self.rois_getter() if self.rois_getter else []
        sx, sy = w / self.main[0], h / self.main[1]
        out = []
        if rois:
            for r in rois:
                out.append(((r["x"] + r["w"] / 2) * sx, (r["y"] + r["h"] / 2) * sy, min(r["w"], r["h"]) * sx * 0.22))
        else:
            for i in range(6):
                c, rr = i % 3, i // 3
                out.append((w * (0.2 + 0.3 * c), h * (0.3 + 0.4 * rr), min(w, h) * 0.11))
        return out

    def render(self, w: int, h: int, t: float | None = None) -> np.ndarray:
        t = time.time() if t is None else t
        rng = np.random.default_rng(self.seed)
        img = np.full((h, w, 3), (132, 138, 142), np.uint8)            # neutral grey board (BGR)
        step = max(8, int(w / 62))                                        # ~1 cm grid at 62 cm frame
        for x in range(step // 2, w, step):
            for y in range(step // 2, h, step):
                img[y, x] = (90, 96, 100)
        for i, (cx, cy, rad) in enumerate(self._blob_centres(w, h)):
            jitter = 1 + 0.03 * math.sin(t / 3 + i)
            ax = int(rad * jitter * (1.15 + 0.1 * rng.random()))
            ay = int(rad * jitter * (0.9 + 0.1 * rng.random()))
            col = (int(60 + 10 * rng.random()), int(150 + 20 * rng.random()), int(70 + 10 * rng.random()))
            cv2.ellipse(img, (int(cx), int(cy)), (ax, ay), float(20 * i), 0, 360, col, -1)
            for k in range(5):                                           # leaf lobes
                ang = k * 72 + 15 * i
                lx = int(cx + ax * 0.85 * math.cos(math.radians(ang)))
                ly = int(cy + ay * 0.85 * math.sin(math.radians(ang)))
                cv2.ellipse(img, (lx, ly), (int(ax * 0.45), int(ay * 0.3)), float(ang), 0, 360, col, -1)
        noise = rng.integers(-6, 7, size=img.shape, dtype=np.int16)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        gain = float(self.controls.get("AnalogueGain", 2.0))
        if self.auto:
            gain = 1.6
        img = np.clip(img.astype(np.float32) * (0.85 + 0.1 * gain), 0, 255).astype(np.uint8)
        cv2.putText(img, "FAKE CAMERA", (12, max(24, int(h * 0.05))), cv2.FONT_HERSHEY_SIMPLEX,
                    max(0.5, h / 900), (40, 40, 200), 2)
        return img

    def capture_array(self) -> np.ndarray:
        return self.render(*self.lores)

    def capture_file(self, path: str) -> None:
        os.makedirs(os.path.dirname(str(path)) or ".", exist_ok=True)
        cv2.imwrite(str(path), self.render(*self.main), [cv2.IMWRITE_JPEG_QUALITY, 90])


def picamera2_importable() -> tuple[bool, str]:
    try:
        import picamera2  # noqa: F401
        return True, ""
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def make_backend(mode: str, rois_getter=None, log=print) -> CameraBackend:
    if mode == "fake":
        return FakeBackend(rois_getter, log=log)
    ok, why = picamera2_importable()
    if mode == "picamera2":
        if not ok:
            raise CameraUnavailable(f"picamera2 not importable: {why}")
        return Picamera2Backend(log=log)
    return Picamera2Backend(log=log) if ok else FakeBackend(rois_getter, log=log)
