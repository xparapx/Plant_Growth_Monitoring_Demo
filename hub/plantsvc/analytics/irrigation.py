"""Irrigation: the recent-events table and the '관수 기록' summary (manual §17 item 3)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..db import Frames
from ..timeutil import iso_utc
from .roster import Roster

ML_PER_SEC = 10.0   # Watering Unit U101 pump, measured with a cup (water_node.ino ML_PER_SEC)


def recent(fr: Frames, roster: Roster, n: int = 5) -> dict[str, Any]:
    pump = fr.pump
    if pump.empty:
        return {"rows": []}
    t = pump.sort_values("ts", ascending=False).head(n)
    now = fr.now
    rows = []
    for r in t.itertuples():
        ago_h = int((now - r.ts).total_seconds() // 3600) if now is not None else None
        before = None if pd.isna(r.soil_before) else round(float(r.soil_before), 1)
        after = None if pd.isna(r.soil_after) else round(float(r.soil_after), 1)
        rows.append({"ts": iso_utc(r.ts.to_pydatetime()), "ago_h": ago_h,
                     "pot": str(r.plant_id).upper(), "plant_id": r.plant_id,
                     "treat": (roster.treat.get(r.plant_id) or "").upper() or None,
                     "pump_s": None if pd.isna(r.dur_ms) else round(float(r.dur_ms) / 1000, 1),
                     "before": before, "after": after,
                     "rise": None if before is None or after is None else round(after - before, 1),
                     "reason": None if pd.isna(r.reason) else str(r.reason).replace("_", " ")})
    return {"rows": rows}


def water_summary(fr: Frames, roster: Roster, tz: str, days: int = 14) -> dict[str, Any]:
    """Per-group cumulative water (mL) and per-pot dose interval trend - an OUTCOME, not a control."""
    pump = fr.pump
    out: dict[str, Any] = {"ml_per_s": ML_PER_SEC, "groups": {}, "pots": [], "daily": {"days": [], "groups": {}}}
    if pump.empty or "dur_ms" not in pump.columns:
        return out
    p = pump.dropna(subset=["dur_ms"]).copy()
    p["ml"] = p.dur_ms.astype(float) / 1000 * ML_PER_SEC
    p["treat"] = p.plant_id.map(roster.treat)
    p = p[p.treat.notna()]
    if p.empty:
        return out
    for k, sub in p.groupby("treat"):
        out["groups"][k] = {"total_ml": round(float(sub.ml.sum()), 1), "events": int(len(sub)),
                            "pots": int(sub.plant_id.nunique()),
                            "ml_per_pot": round(float(sub.ml.sum() / max(1, sub.plant_id.nunique())), 1)}
    for pid in roster.pots:
        sub = p[p.plant_id == pid].sort_values("ts")
        if sub.empty:
            continue
        gaps = sub.ts.diff().dt.total_seconds().dropna() / 86400
        out["pots"].append({"plant_id": pid, "treat": roster.treat.get(pid), "events": int(len(sub)),
                            "total_ml": round(float(sub.ml.sum()), 1),
                            "interval_d": [round(float(x), 2) for x in gaps],
                            "mean_interval_d": None if gaps.empty else round(float(gaps.mean()), 2),
                            "last_interval_d": None if gaps.empty else round(float(gaps.iloc[-1]), 2)})
    p["day"] = p.ts.dt.tz_convert(tz).dt.date.astype(str)
    daily = p.groupby(["day", "treat"]).ml.sum().unstack().fillna(0.0).iloc[-days:]
    out["daily"] = {"days": list(daily.index),
                    "groups": {k: [round(float(v), 1) for v in daily[k]] for k in daily.columns}}
    return out
