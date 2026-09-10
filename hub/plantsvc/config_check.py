"""Consistency check of config.json - port of hub/check_config.py.

Showing numbers is secondary; the point is to catch contradictions before the
6-week run starts (ROI outside the frame, overlapping ROIs, missing scale...).
"""

from __future__ import annotations

from typing import Any

from .config_model import TREATS, Config


def check(cfg: Config | dict[str, Any]) -> dict[str, Any]:
    C = cfg.to_legacy_dict() if isinstance(cfg, Config) else cfg
    bad: list[str] = []
    warn: list[str] = []
    lines: list[dict[str, Any]] = []

    def line(section: str, k: str, v: Any, note: str = "") -> None:
        lines.append({"section": section, "k": k, "v": v, "note": note})

    cap = C.get("capture", {})
    size = cap.get("size", [0, 0])
    W, H = size if len(size) == 2 else (0, 0)
    qc = C.get("qc", {})
    ppc = float(qc.get("px_per_cm_ref", 0) or 0)
    rois = C.get("rois", [])

    # -- capture -------------------------------------------------------------
    line("촬영 조건", "해상도", f"{W} x {H} px")
    line("촬영 조건", "lens_position", cap.get("lens_position"), "디옵터 = 1/거리(m)")
    exp = cap.get("exposure_us")
    line("촬영 조건", "exposure_us", exp, f"= 1/{1e6 / exp:.0f} 초" if exp else "")
    line("촬영 조건", "gain", cap.get("gain"))
    line("촬영 조건", "colour_gains", cap.get("colour_gains"), "(적색, 청색)")
    g = float(cap.get("gain", 0) or 0)
    if g > 4:
        warn.append(f"gain {g} — 조명이 어둡습니다. 노이즈가 ExG 분리를 방해합니다")
    if not cap.get("lens_position"):
        bad.append("lens_position 이 비어 있습니다 — [자동 측정] 을 실행하세요")

    # -- scale ---------------------------------------------------------------
    if ppc > 0:
        line("배율", "px_per_cm_ref", f"{ppc:.1f} px/cm")
        line("배율", "프레임 실제 크기", f"{W / ppc:.1f} x {H / ppc:.1f} cm")
        line("배율", "1 px", f"{10 / ppc:.2f} mm")
    else:
        line("배율", "px_per_cm_ref", "없음")
        bad.append("px_per_cm_ref 가 0 입니다 — area_cm2 가 null 이 되고 측정 행이 ok=0 으로 "
                   "기록되어 대시보드가 전부 걸러냅니다")

    # -- rois ----------------------------------------------------------------
    line("ROI", "칸 수", len(rois))
    if not rois:
        bad.append("rois 가 비어 있습니다 — [잎 찾아 배치] 또는 [격자로 나누기] 를 누르세요")
    counts: dict[str, int] = {}
    seen: set[str] = set()
    for r in rois:
        t = r.get("treat") or "(빈칸)"
        counts[t] = counts.get(t, 0) + 1
        x, y, w, h = r.get("x", 0), r.get("y", 0), r.get("w", 0), r.get("h", 0)
        cm = f"{w / ppc:.1f} x {h / ppc:.1f} cm" if ppc > 0 else ""
        flag = ""
        if x < 0 or y < 0 or x + w > W or y + h > H:
            flag = "화면 밖!"
            bad.append(f'{r.get("plant_id")} 의 ROI 가 프레임을 벗어납니다')
        line("ROI", f'{r.get("plant_id")}  [{t}]', f"({x},{y}) {w}x{h} px  {cm}", flag)
        if t not in TREATS:
            bad.append(f'{r.get("plant_id")} 의 treat 가 "{t}" 입니다 — stable / fluct 만 인식합니다')
        pid = r.get("plant_id")
        if pid in seen:
            bad.append(f"plant_id {pid} 가 중복입니다")
        seen.add(pid)
    for i in range(len(rois)):
        for j in range(i + 1, len(rois)):
            a, b = rois[i], rois[j]
            ox = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
            oy = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
            if ox > 0 and oy > 0:
                bad.append(f'{a["plant_id"]} 와 {b["plant_id"]} 의 ROI 가 겹칩니다 '
                           f"({ox}x{oy} px) — 잎이 두 번 세어집니다")

    for t, n in sorted(counts.items()):
        line("처리군", t, f"{n} 칸")
    if len(counts) == 2 and len(set(counts.values())) > 1:
        warn.append("두 처리군의 화분 수가 다릅니다 — 비교의 검정력이 떨어집니다")
    if rois and len(counts) == 1:
        warn.append("처리군이 한 종류뿐입니다 — [무작위 배정] 을 누르세요")

    lay = C.get("layout", {})
    pot = float(lay.get("pot_cm", 0) or 0)
    if ppc > 0 and pot > 0 and rois:
        side_cm = min(min(r["w"], r["h"]) for r in rois) / ppc
        line("여유", "화분 지름", f"{pot:.0f} cm")
        line("여유", "가장 작은 ROI 한 변", f"{side_cm:.1f} cm", f"= 화분의 {side_cm / pot:.1f} 배")
        if side_cm < pot * 1.5:
            warn.append(f"ROI 가 화분 지름의 {side_cm / pot:.1f} 배뿐입니다 — 6주 뒤 잎이 박스 밖으로 "
                        "나가면 그때부터 면적이 잘립니다 (1.5~2 배 권장)")

    # -- schedule / led --------------------------------------------------------
    led = C.get("led", {})
    sched = C.get("schedule", {})
    line("스케줄", "dawn / pm", f'{sched.get("dawn")} / {sched.get("pm")}', f'tz {C.get("tz")}')
    line("LED", "enabled / driver", f'{led.get("enabled")} / {led.get("driver")}',
         f'pin {led.get("pin")} warm-up {led.get("warmup_s")}s')
    if led.get("enabled"):
        try:
            from .timeutil import add_minutes, seconds_between_hhmm
            shot = add_minutes(sched.get("dawn", "05:50"), int(led.get("warmup_s", 300)) // 60 + 2)
            if seconds_between_hhmm(shot, "06:00") < 0:
                warn.append(f"dawn {sched.get('dawn')} + 워밍업 {led.get('warmup_s')}s 면 촬영이 "
                            f"06:00 을 넘습니다 ({shot}) — dawn 을 앞당기세요")
        except Exception:
            pass

    return {"bad": bad, "warn": warn, "lines": lines, "ok": not bad}


def format_report(rep: dict[str, Any]) -> str:
    out = []
    cur = None
    for ln in rep["lines"]:
        if ln["section"] != cur:
            cur = ln["section"]
            out.append(f"\n[{cur}]")
        out.append(f"  {ln['k']:<22} {ln['v']}" + (f"   {ln['note']}" if ln["note"] else ""))
    out.append("")
    for w in rep["warn"]:
        out.append(f"  주의  {w}")
    for b in rep["bad"]:
        out.append(f"  문제  {b}")
    if not rep["bad"]:
        out.append("  ✔ 치명적인 문제 없음 — 촬영·측정을 시작해도 됩니다")
    out.append("")
    return "\n".join(out)
