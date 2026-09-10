"""Camera-setup actions - the ACTIONS table of setup_camera.py as a session object.

Every action persists config.json atomically (as persist() did).  Click
coordinates arrive in PREVIEW pixels (1280x720 by default) exactly as before;
conversion to capture coordinates uses cfg.scale.
"""

from __future__ import annotations

import os
import random
import threading
from typing import Any

import cv2
import numpy as np

from ..config_model import Roi
from ..vision import frame_align, roi_tools
from .manager import CameraBusy


class SetupSession:
    def __init__(self, store, camera, paths, events=None, hub=None):
        self.store, self.camera, self.paths = store, camera, paths
        self.events, self.hub = events, hub
        self._lock = threading.RLock()
        self.msg = "준비됨"
        self.level = "info"
        self.pts: list[list[float]] = []
        self.ppc_fixed: float | None = None
        self.cm: float = 0.0
        self.order: list[int] | None = None
        self.last_auto: dict[str, Any] | None = None
        self._drift_cache: tuple[tuple, dict[str, Any]] | None = None

    # ---- status -------------------------------------------------------------------
    def step_done(self) -> dict[str, bool]:
        cfg = self.store.get()
        rois = cfg.rois
        return {"focus": bool(cfg.capture.lens_position and cfg.capture.exposure_us),
                "scale": bool(cfg.qc.px_per_cm_ref),
                "roi": bool(rois),
                "treat": bool(rois) and all(r.treat in ("stable", "fluct") for r in rois),
                "shot": self.paths.calib.exists()}

    def latest_raw(self) -> str | None:
        try:
            files = sorted(p for p in os.listdir(self.paths.raw) if p.endswith(".jpg") and not p.startswith("fake_"))
        except FileNotFoundError:
            return None
        return files[-1] if files else None

    def status(self) -> dict[str, Any]:
        cfg = self.store.get()
        d = self.step_done()
        calib = self.paths.calib
        cam = self.camera.status()
        return {"msg": self.msg, "msg_level": self.level, "done": d, "all": all(d.values()),
                "mode": cfg.treat_mode, "naming": self.order is not None,
                "order": list(self.order) if self.order is not None else None,
                "pots": [{"id": r.plant_id, "treat": r.treat} for r in cfg.rois],
                "rois": [{**r.model_dump(), "out": self._out_of_frame(r, cfg)} for r in cfg.rois],
                "ppc": round(self.ppc_fixed or cfg.qc.px_per_cm_ref or 0, 1),
                "nroi": len(cfg.rois), "cm": float(self.cm or 0), "pts": [list(p) for p in self.pts],
                "pot_cm": cfg.layout.pot_cm,
                "capture": cfg.capture.model_dump(), "last_auto": self.last_auto,
                "calib": {"exists": calib.exists(),
                          "mtime": int(calib.stat().st_mtime) if calib.exists() else None,
                          "url": "/api/camera/calib.jpg" if calib.exists() else None},
                "latest_raw": self.latest_raw(),
                **{k: cam[k] for k in ("state", "driver", "clients", "preview", "paused_for", "error",
                                        "preview_size", "capture_size", "scale", "lock_holder_pid",
                                        "ops_busy", "quiet_window")}}

    @staticmethod
    def _out_of_frame(r: Roi, cfg) -> bool:
        W, H = cfg.capture.size
        return r.x < 0 or r.y < 0 or r.x + r.w > W or r.y + r.h > H

    # ---- dispatch -------------------------------------------------------------------
    def run(self, name: str, p: dict[str, Any] | None = None) -> dict[str, Any]:
        p = p or {}
        fn = getattr(self, f"act_{name}", None)
        if fn is None:
            raise KeyError(name)
        with self._lock:
            if name not in ("open", "close", "save") and self.camera.ops_busy == "job":
                raise CameraBusy("capture in progress — setup actions are locked until it finishes")
            try:
                msg = fn(p)
                self.level = "warn" if "⚠" in msg else ("good" if any(k in msg for k in ("완료", "저장", "기록")) else "info")
            except CameraBusy as e:
                msg, self.level = f"⚠ {e}", "warn"
            self.msg = msg
            if self.events is not None:
                try:
                    self.events.add(f"setup.{name}", {"msg": msg})
                except Exception:
                    pass
        st = self.status()
        if self.hub is not None:
            self.hub.broadcast("camera.setup", {"action": name, "msg": msg, "done": st["done"]})
        return {"msg": msg, "status": st}

    # ---- actions ----------------------------------------------------------------------
    def act_open(self, p):
        self.camera.ensure_open()
        return "카메라 열림"

    def act_close(self, p):
        self.camera.close()
        return "카메라 닫음 — 예약 촬영이 쓸 수 있습니다"

    def act_save(self, p):
        self.store.save(self.store.get())
        return "현재 설정을 다시 저장했습니다"

    def act_auto(self, p):
        vals = self.camera.auto_cycle()
        self.last_auto = vals

        def _u(c):
            c.capture.exposure_us = int(vals["exposure_us"])
            c.capture.gain = float(vals["gain"])
            c.capture.colour_gains = (float(vals["colour_gains"][0]), float(vals["colour_gains"][1]))
            c.capture.lens_position = float(vals["lens_position"])
        self.store.update(_u)
        gain = vals["gain"]
        warn = ""
        if gain > 4.0:
            warn = f"  ⚠ gain {gain:.1f} 은 높습니다 — 조명을 밝게 하고 다시 측정하세요(노이즈)"
        elif gain > 2.0:
            warn = "  · 조명을 더 밝게 하면 노이즈가 줄어듭니다"
        cg = vals["colour_gains"]
        return (f"exp {vals['exposure_us']} · gain {gain:.2f} · WB {cg[0]:.2f}/{cg[1]:.2f} · "
                f"lens {vals['lens_position']:.2f}  — 고정·저장 완료{warn}")

    def act_point(self, p):
        x, y, cm = float(p["x"]), float(p["y"]), float(p.get("cm", self.cm or 10))
        cfg = self.store.get()
        pts = self.pts if len(self.pts) < 2 else []
        pts.append([x, y])
        self.pts = pts
        self.cm = cm
        if len(pts) < 2:
            return "첫 점 찍음 — 반대쪽 끝을 한 번 더 클릭하세요"
        d_prev = float(np.hypot(pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]))
        d_cap = d_prev / cfg.scale
        if cm <= 0 or d_cap <= 0:
            return "길이가 0입니다"
        ppc = d_cap / cm
        self.ppc_fixed = ppc

        def _u(c):
            c.qc.px_per_cm_ref = round(ppc, 1)
        self.store.update(_u)
        frame_cm = cfg.capture.size[0] / ppc
        lay = cfg.layout
        need = lay.cols * lay.pot_cm + (lay.cols - 1) * lay.gap_cm
        warn = ""
        if lay.pot_cm and frame_cm < need:
            warn = f"   ⚠ 프레임 폭 {frame_cm:.0f}cm 가 배치 {need:.0f}cm 보다 좁습니다 — 다시 재세요"
        elif lay.pot_cm and frame_cm > need * 3:
            warn = f"   ⚠ 프레임 폭 {frame_cm:.0f}cm 는 배치 {need:.0f}cm 의 3배가 넘습니다 — 길이 입력칸을 확인하세요"
        return f"{d_cap:.0f}px(원본) / {cm:g}cm  ->  {ppc:.1f} px/cm  · 프레임 폭 {frame_cm:.0f}cm · 기록{warn}"

    def act_clearpoints(self, p):
        self.pts = []
        return "배율 측정점 초기화"

    def act_setpot(self, p):
        cm = float(p.get("pot_cm", 0))
        if cm <= 0:
            return "0보다 큰 값을 넣으세요"

        def _u(c):
            c.layout.pot_cm = cm
        self.store.update(_u)
        return f"화분 지름 {cm:g} cm 기록 — 배율 검산에 쓰입니다"

    def act_shoot(self, p):
        cfg = self.store.get()
        with self.camera.exclusive(timeout=30, label="shoot"):
            self.camera.capture_still(self.paths.calib)
        self._drift_cache = None
        W, H = cfg.capture.size
        return f"calib.jpg 저장 ({W}x{H}) — 완료"

    def act_findleaf(self, p):
        cfg = self.store.get()
        with self.camera.exclusive(timeout=30, label="findleaf"):
            frame = self.camera.preview_frame()
        blobs = roi_tools.leaf_blobs(frame)
        if not blobs:
            return "초록 덩어리를 못 찾았습니다 — 조명·초점을 먼저 맞추세요"
        existing = [r.model_dump() for r in cfg.rois]
        rois, info = roi_tools.place_from_blobs(blobs, scale=cfg.scale, cap_w=cfg.capture.size[0],
                                                cap_h=cfg.capture.size[1], existing=existing)

        def _u(c):
            c.rois = [Roi(**r) for r in rois]
        self.store.update(_u)
        same = "모두 같음" if info["same"] else "★ 다름"
        tail = "처리군 유지됨" if info["kept"] else "처리군이 비었습니다 — 다시 배정하세요"
        return f"잎 {info['n']}개 — 중심만 이동 · {info['how']} · 크기 {same} · {tail} · 저장"

    def act_autoroi(self, p):
        cfg = self.store.get()
        cols, rows = int(p.get("cols", cfg.layout.cols)), int(p.get("rows", cfg.layout.rows))
        rois = roi_tools.grid_rois(cfg.capture.size[0], cfg.capture.size[1], cols, rows)

        def _u(c):
            c.rois = [Roi(**r) for r in rois]
            c.layout.cols, c.layout.rows = cols, rows
        self.store.update(_u)
        return f"{cols}x{rows} 격자 = {len(rois)}칸 — 처리군은 아직 비어 있습니다 · 저장"

    def act_rename(self, p):
        n = len(self.store.get().rois)
        if n == 0:
            return "ROI 가 없습니다 — 먼저 배치하세요"
        self.order = []
        return f"이름을 붙일 순서대로 화면의 박스를 클릭하세요 (0/{n})"

    def act_cancel_naming(self, p):
        self.order = None
        return "이름 지정 취소"

    def act_pickroi(self, p):
        if self.order is None:
            return "먼저 [이름 다시 매기기] 를 누르세요"
        cfg = self.store.get()
        X, Y = float(p["x"]) / cfg.scale, float(p["y"]) / cfg.scale
        rois = [r.model_dump() for r in cfg.rois]
        i = roi_tools.hit_roi(rois, X, Y)
        if i is None:
            return "박스 안을 클릭하세요"
        if i in self.order:
            return "이미 고른 박스입니다"
        self.order.append(i)
        n = len(rois)
        if len(self.order) < n:
            return f"{len(self.order)}/{n} — 다음 박스를 클릭하세요"
        new = roi_tools.rename_by_order(rois, self.order)
        self.order = None

        def _u(c):
            c.rois = [Roi(**r) for r in new]
        self.store.update(_u)
        return "이름 지정 완료 — " + " · ".join(f"{r['plant_id']}(x={r['x']})" for r in new)

    def act_settreat(self, p):
        pid, treat = str(p.get("pid")), str(p.get("treat"))
        if treat not in ("stable", "fluct"):
            return f"알 수 없는 처리군: {treat}"
        cfg = self.store.get()
        if not any(r.plant_id == pid for r in cfg.rois):
            return f"{pid} 를 찾을 수 없습니다"

        def _u(c):
            for r in c.rois:
                if r.plant_id == pid:
                    r.treat = treat
            c.treat_mode = "manual"
        self.store.update(_u)
        return f"{pid} → {treat} (직접 지정) · 저장"

    def act_shuffle(self, p):
        cfg = self.store.get()
        rois = [r.model_dump() for r in cfg.rois]
        err = roi_tools.shuffle_treat(rois, random.Random(p.get("seed")) if p.get("seed") is not None else None)
        if err:
            return err

        def _u(c):
            c.rois = [Roi(**r) for r in rois]
            c.treat_mode = "random"
        self.store.update(_u)
        return "무작위 배정 완료 — " + " ".join(f'{r["plant_id"]}:{r["treat"][0]}' for r in rois)

    def act_centerroi(self, p):
        cfg = self.store.get()
        which = p.get("image", "calib")
        src = self.paths.calib if which == "calib" else (self.paths.raw / (self.latest_raw() or ""))
        if not src.exists() or src.is_dir():
            return "사진이 없습니다 — 먼저 [촬영] 하세요"
        img = cv2.imread(str(src))
        if img is None:
            return f"못 읽음: {src.name}"
        rois = [r.model_dump() for r in cfg.rois]
        if not rois:
            return "ROI 가 없습니다"
        props = roi_tools.center_proposals(img, rois)
        out = self.paths.data_dir / "roi_offset.jpg"
        cv2.imwrite(str(out), roi_tools.draw_center_overlay(img, props))
        self.last_center = props
        moved = sum(1 for q in props if q["found"] and (q["dx"] or q["dy"]))
        if not p.get("apply"):
            return f"제안 {moved}개 이동 (미적용) — /api/images/data/roi_offset.jpg 에서 확인"
        if moved == 0:
            return "이미 맞습니다. 바꿀 것 없음"
        roi_tools.apply_center_proposals(rois, props)

        def _u(c):
            c.rois = [Roi(**r) for r in rois]
        self.store.update(_u)
        self._drift_cache = None
        return f"ROI 재중심 적용 — {moved}개 이동 · 크기 불변 · 저장"

    # ---- drift (on demand, cached) -------------------------------------------------------
    def drift(self) -> dict[str, Any]:
        cfg = self.store.get()
        latest = self.latest_raw()
        if not self.paths.calib.exists():
            return {"level": "unknown", "msg": "calib.jpg 가 없습니다", "ok": False, "cur": None}
        if not latest:
            return {"level": "unknown", "msg": "촬영된 사진이 아직 없습니다", "ok": False, "cur": None}
        cur = self.paths.raw / latest
        key = (latest, int(cur.stat().st_mtime), int(self.paths.calib.stat().st_mtime), self.store.mtime_ns)
        if self._drift_cache and self._drift_cache[0] == key:
            return self._drift_cache[1]
        d = frame_align.align(str(cur), str(self.paths.calib), cfg.to_legacy_dict(), log=None)
        d["cur"] = latest
        ppc = cfg.qc.px_per_cm_ref
        d["mag_mm"] = round(d.get("mag", 0) / ppc * 10, 2) if ppc else None
        self._drift_cache = (key, d)
        return d
