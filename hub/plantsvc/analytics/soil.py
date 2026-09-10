"""Soil-moisture analytics: validity (the headline), distributions, weekly alignment."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..config_model import Config
from ..db import Frames
from .roster import Roster


def _group_series(soil: pd.DataFrame, roster: Roster) -> pd.core.groupby.SeriesGroupBy | None:
    if soil.empty or "pct" not in soil.columns:
        return None
    g = soil.plant_id.map(roster.treat)
    return soil[g.notna()].groupby(g[g.notna()]).pct


def validity(fr: Frames, roster: Roster, cfg: Config) -> dict[str, Any]:
    tol, sep = cfg.analysis.tol_pp, cfg.analysis.sep_ratio
    out: dict[str, Any] = {"tol_pp": tol, "sep_ratio": sep, "enough_groups": False,
                           "groups": roster.groups, "mu": {}, "sd": {}, "n": {},
                           "dmu": None, "aligned": None, "ratio": None, "separated": None}
    g = _group_series(fr.soil, roster)
    if g is None:
        return out
    mu, sd, n = g.mean(), g.std(), g.size()
    out["mu"] = {k: round(float(v), 3) for k, v in mu.items()}
    out["sd"] = {k: round(float(v), 3) for k, v in sd.items() if pd.notna(v)}
    out["n"] = {k: int(v) for k, v in n.items()}
    if "stable" in mu and "fluct" in mu and pd.notna(sd.get("stable")) and sd["stable"] > 0:
        dmu = abs(float(mu["stable"] - mu["fluct"]))
        ratio = float(sd["fluct"] / sd["stable"])
        out.update(enough_groups=True, dmu=round(dmu, 3), aligned=dmu <= tol,
                   ratio=round(ratio, 3), separated=ratio >= sep)
    return out


def histogram(fr: Frames, roster: Roster, cfg: Config, bins: int | None = None) -> dict[str, Any]:
    bins = bins or cfg.analysis.hist_bins
    soil = fr.soil
    out: dict[str, Any] = {"edges": [], "groups": {}, "e_w": None,
                           "quantiles": {"p05": None, "p95": None, "mean": None}}
    if soil.empty or "pct" not in soil.columns:
        return out
    g = soil.plant_id.map(roster.treat)
    vals = soil[g.notna()].pct.dropna()
    if vals.empty:
        return out
    lo, hi = float(vals.min()), float(vals.max())
    if hi <= lo:
        hi = lo + 1.0
    edges = np.linspace(lo, hi, bins + 1)
    out["edges"] = [round(float(e), 3) for e in edges]
    mus = []
    for k in roster.groups:
        v = soil[g == k].pct.dropna()
        if v.empty:
            continue
        cnt, _ = np.histogram(v.to_numpy(), bins=edges)
        prob = cnt / max(1, len(v))
        out["groups"][k] = {"prob": [round(float(p), 5) for p in prob],
                            "mu": round(float(v.mean()), 3), "sd": round(float(v.std()), 3),
                            "n": int(len(v))}
        mus.append(float(v.mean()))
    if len(mus) == 2:
        out["e_w"] = round(float(np.mean(mus)), 3)
    out["quantiles"] = {"p05": round(float(vals.quantile(.05)), 3),
                        "p95": round(float(vals.quantile(.95)), 3),
                        "mean": round(float(vals.mean()), 3)}
    return out


def alignment_trend(fr: Frames, roster: Roster, cfg: Config) -> dict[str, Any]:
    soil = fr.soil
    if soil.empty or "pct" not in soil.columns:
        return {"weeks": [], "groups": {}}
    wk = soil.copy()
    loc = wk.ts.dt.tz_convert(cfg.tz)
    iso = loc.dt.isocalendar()
    wk["week"] = iso.year.astype(str) + "-W" + iso.week.astype(int).map(lambda w: f"{w:02d}")
    grp = wk.plant_id.map(roster.treat)
    wk = wk[grp.notna()]
    tbl = wk.groupby(["week", grp[grp.notna()]]).pct.mean().unstack()
    weeks = list(tbl.index)
    groups = {k: [None if pd.isna(v) else round(float(v), 3) for v in tbl[k]]
              for k in roster.groups if k in tbl}
    return {"weeks": weeks, "groups": groups}


def reference(fr: Frames) -> dict[str, Any]:
    """Inputs for the collapsed 'how to read' curves (the curves themselves are UI constants)."""
    v = fr.soil.pct.dropna() if len(fr.soil) and "pct" in fr.soil.columns else pd.Series(dtype=float)
    if v.empty:
        return {"p05": None, "p95": None, "mean": None}
    return {"p05": round(float(v.quantile(.05)), 3), "p95": round(float(v.quantile(.95)), 3),
            "mean": round(float(v.mean()), 3)}


def soil_series(fr: Frames, roster: Roster, cfg: Config, bucket_s: int, pots: list[str] | None = None,
                basis: str = "pct") -> dict[str, Any]:
    from ..db import resample_columns
    soil = fr.soil
    band = cfg.bands.band_pct()
    lo = min([float(soil.pct.min()) if len(soil) else np.inf] + [b[0] for b in band.values()])
    hi = max([float(soil.pct.max()) if len(soil) else -np.inf] + [b[1] for b in band.values()])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo, hi = 20.0, 85.0
    pad = max(2.0, (hi - lo) * .06)
    yrange = [max(0.0, lo - pad), min(100.0, hi + pad)]
    out: dict[str, Any] = {"basis": basis, "band_pct": {k: [round(a, 2), round(b, 2)] for k, (a, b) in band.items()},
                           "yrange": [round(yrange[0], 2), round(yrange[1], 2)], "pots": []}
    if soil.empty:
        return out
    d = soil
    if basis == "raw" and "raw" in d.columns and d.raw.notna().any():
        d = d.copy()
        d["pct"] = [cfg.bands.pct_of(r, p) if pd.notna(r) else np.nan for r, p in zip(d.raw, d.plant_id, strict=True)]
    want = pots or roster.pots
    for p in want:
        s = d[d.plant_id == p]
        if s.empty:
            continue
        r = resample_columns(s, ["pct"], bucket_s)
        out["pots"].append({"plant_id": p, "treat": roster.treat.get(p),
                            "ts": [t.strftime("%Y-%m-%dT%H:%M:%SZ") for t in r.ts],
                            "pct": [None if pd.isna(v) else round(float(v), 2) for v in r.pct],
                            "n": [int(x) for x in r["n"]] if "n" in r.columns else None})
    return out
