"""Growth analytics: canopy series, silhouettes, midday droop, RGR + Cohen's d."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from ..config_model import Config
from ..db import Frames
from ..timeutil import iso_utc
from .roster import Roster


def _dawn(fr: Frames) -> pd.DataFrame:
    g = fr.grow
    if g.empty:
        return g
    return g[g.phase == "dawn"] if "phase" in g.columns else g


def _iso(ts) -> str | None:
    return iso_utc(ts.to_pydatetime()) if ts is not None and pd.notna(ts) else None


def canopy_series(fr: Frames, roster: Roster, phase: str = "dawn") -> dict[str, Any]:
    g = fr.grow
    if g.empty:
        return {"pots": []}
    if phase != "all" and "phase" in g.columns:
        g = g[g.phase == phase]
    pots = []
    for p in roster.pots:
        d = g[g.plant_id == p].sort_values("ts")
        if d.empty:
            continue
        pots.append({"plant_id": p, "treat": roster.treat.get(p),
                     "ts": [_iso(t) for t in d.ts],
                     "area_cm2": [None if pd.isna(v) else round(float(v), 2) for v in d.area_cm2]})
    return {"pots": pots}


def silhouettes(fr: Frames, roster: Roster) -> dict[str, Any]:
    dawn = _dawn(fr)
    out: dict[str, Any] = {"pots": [], "not_enough": []}
    if dawn.empty or "contour" not in dawn.columns:
        out["not_enough"] = list(roster.pots)
        return out
    for treat, members in roster.groups.items():
        for p in members:
            d = dawn[dawn.plant_id == p].dropna(subset=["contour"]).sort_values("ts")
            if len(d) < 2:
                out["not_enough"].append(p)
                continue
            new = d.iloc[-1]
            older = d[d.ts <= new.ts - pd.Timedelta(days=1)]
            old = older.iloc[-1] if len(older) else d.iloc[0]
            gap_d = (new.ts - old.ts).total_seconds() / 86400
            gain = 100 * (new.area_px - old.area_px) / old.area_px if old.area_px else None
            base = d.iloc[0]
            span_d = (new.ts - base.ts).total_seconds() / 86400
            tot = (100 * (new.area_px - base.area_px) / base.area_px) if base.area_px else None
            try:
                new_c = json.loads(new.contour)
                old_c = json.loads(old.contour)
            except (TypeError, ValueError):
                out["not_enough"].append(p)
                continue
            lim = float(np.abs(np.array(new_c)).max()) * 1.12 if new_c else 1.0

            def row(r, c):
                return {"ts": _iso(r.ts), "area_cm2": None if pd.isna(r.area_cm2) else round(float(r.area_cm2), 2),
                        "area_px": int(r.area_px), "contour": c}
            out["pots"].append({"plant_id": p, "treat": treat, "new": row(new, new_c),
                                "old": row(old, old_c), "gain_pct": None if gain is None else round(float(gain), 1),
                                "gap_d": round(gap_d, 2),
                                "base": {"ts": _iso(base.ts), "area_cm2": None if pd.isna(base.area_cm2) else round(float(base.area_cm2), 2)},
                                "total_pct": None if tot is None else round(float(tot), 1),
                                "span_d": round(span_d, 2), "lim": round(lim, 1)})
    return out


def droop(fr: Frames, roster: Roster, cfg: Config) -> dict[str, Any]:
    g = fr.grow
    out: dict[str, Any] = {"rows": [], "missing": list(roster.pots), "has_both_phases": False}
    if g.empty or "phase" not in g.columns or not {"dawn", "pm"} <= set(g.phase.unique()):
        return out
    out["has_both_phases"] = True
    g2 = g.copy()
    g2["day"] = g2.ts.dt.tz_convert(cfg.tz).dt.date.astype(str)
    pv = g2.pivot_table(index=["day", "plant_id"], columns="phase", values="area_px").dropna()
    if pv.empty:
        return out
    pv["droop"] = 100 * (pv.dawn - pv.pm) / pv.dawn
    last = pv.reset_index().groupby("plant_id").last().reset_index()
    have = [p for p in roster.pots if p in set(last.plant_id)]
    last = last.set_index("plant_id").loc[have].reset_index() if have else last.iloc[0:0]
    out["rows"] = [{"pot": r.plant_id, "treat": roster.treat.get(r.plant_id), "day": r.day,
                    "dawn_px": int(r.dawn), "pm_px": int(r.pm), "droop_pct": round(float(r.droop), 2)}
                   for r in last.itertuples()]
    out["missing"] = [p for p in roster.pots if p not in have]
    return out


def droop_timeline(fr: Frames, roster: Roster, cfg: Config, days: int = 14) -> dict[str, Any]:
    """Daily droop per pot over the last `days` local days (the '3-b' report item as a series)."""
    g = fr.grow
    if g.empty or "phase" not in g.columns:
        return {"days": [], "pots": []}
    g2 = g.copy()
    g2["day"] = g2.ts.dt.tz_convert(cfg.tz).dt.date.astype(str)
    pv = g2.pivot_table(index=["day", "plant_id"], columns="phase", values="area_px").dropna()
    if pv.empty or "dawn" not in pv.columns or "pm" not in pv.columns:
        return {"days": [], "pots": []}
    pv["droop"] = 100 * (pv.dawn - pv.pm) / pv.dawn
    tbl = pv.droop.unstack("plant_id")
    tbl = tbl.iloc[-days:]
    return {"days": list(tbl.index),
            "pots": [{"plant_id": p, "treat": roster.treat.get(p),
                      "droop_pct": [None if pd.isna(v) else round(float(v), 2) for v in tbl[p]]}
                     for p in roster.pots if p in tbl.columns]}


def rgr(fr: Frames, roster: Roster) -> dict[str, Any]:
    dawn = _dawn(fr)
    rows = []
    for p in roster.pots:
        d = dawn[dawn.plant_id == p].sort_values("ts").dropna(subset=["area_cm2"]) if len(dawn) else dawn
        d = d[d.area_cm2 > 0] if len(d) else d
        if len(d) < 3:
            continue
        t = (d.ts - d.ts.iloc[0]).dt.total_seconds().to_numpy() / 86400
        y = np.log(d.area_cm2.to_numpy(dtype=float))
        slope, intercept = np.polyfit(t, y, 1)
        resid = y - (slope * t + intercept)
        denom = ((t - t.mean()) ** 2).sum()
        se = float(np.sqrt((resid ** 2).sum() / (len(t) - 2) / denom)) if len(t) > 2 and denom > 0 else float("nan")
        ss_tot = ((y - y.mean()) ** 2).sum()
        r2 = float(1 - (resid ** 2).sum() / ss_tot) if ss_tot > 0 else 1.0
        rows.append({"pot": p, "treat": roster.treat.get(p), "rgr": round(float(slope), 5),
                     "se": None if np.isnan(se) else round(se, 5),
                     "ci95": None if np.isnan(se) else [round(float(slope - 1.96 * se), 5), round(float(slope + 1.96 * se), 5)],
                     "r2": round(r2, 4), "n": int(len(t))})
    out: dict[str, Any] = {"pots": rows, "groups": {}, "cohens_d": None, "effect": None,
                           "worst_r2": None, "comparable": False}
    if not rows:
        return out
    r = pd.DataFrame(rows)
    for k in ("stable", "fluct"):
        sub = r[r.treat == k].rgr
        if len(sub):
            out["groups"][k] = {"mean": round(float(sub.mean()), 5),
                                "sd": None if len(sub) < 2 else round(float(sub.std()), 5),
                                "n": int(len(sub))}
    out["worst_r2"] = round(float(r.r2.min()), 4)
    if r.treat.nunique() == 2 and {"stable", "fluct"} <= set(r.treat):
        a, b = r[r.treat == "stable"].rgr, r[r.treat == "fluct"].rgr
        pooled = np.sqrt(((a.std() if len(a) > 1 else 0) ** 2 + (b.std() if len(b) > 1 else 0) ** 2) / 2)
        if pooled and not np.isnan(pooled):
            d_eff = float((a.mean() - b.mean()) / pooled)
            out["cohens_d"] = round(d_eff, 3)
            out["effect"] = "large" if abs(d_eff) >= .8 else "medium" if abs(d_eff) >= .5 else "small"
        out["comparable"] = True
    return out
