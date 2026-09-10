"""Dashboard data + analytics endpoints."""

from __future__ import annotations

from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, Query

from ..analytics import growth as growth_an
from ..analytics import health as health_an
from ..analytics import irrigation as irr_an
from ..analytics import soil as soil_an
from ..db import BUCKETS, auto_bucket, resample_columns
from ..timeutil import iso_utc, parse_db_ts
from .deps import ApiError, base_meta, ctx

router = APIRouter(prefix="/api", tags=["dashboard"])

DummyQ = Query(None, pattern="^(auto|on|off)$")


def _bucket_s(bucket: str, frm, to, points: int) -> int:
    if bucket == "auto":
        span = (to - frm).total_seconds() if frm is not None and to is not None else 7 * 86400
        return auto_bucket(span, points)
    if bucket not in BUCKETS:
        raise ApiError(400, "bad_bucket", f"bucket must be one of {list(BUCKETS)} or auto")
    return BUCKETS[bucket]


def _window(df: pd.DataFrame, frm: str | None, to: str | None):
    a, b = parse_db_ts(frm), parse_db_ts(to)
    if df.empty:
        return df, a, b
    if a is not None:
        df = df[df.ts >= pd.Timestamp(a)]
    if b is not None:
        df = df[df.ts < pd.Timestamp(b)]
    return df, a or (df.ts.min().to_pydatetime() if len(df) else None), b or (df.ts.max().to_pydatetime() if len(df) else None)


@router.get("/health")
def health(c=Depends(ctx), dummy: str | None = DummyQ) -> dict[str, Any]:
    fr = c.frames(dummy)
    roster = c.roster(fr)
    cfg = c.store.get()
    nodes, alerts = health_an.nodes_and_alerts(fr, roster, cfg)
    return {**base_meta(fr),
            "pots": [{"id": p, "treat": roster.treat.get(p), "real": p in fr.real_pots,
                      "sources": roster.sources.get(p, {})} for p in roster.pots],
            "groups": roster.groups, "unknown_labels": roster.unknown, "suggested_sql": roster.suggested_sql(),
            "conflicts": [{"pot": p, "sources": v} for p, v in sorted(roster.conflicts.items())],
            "nodes": nodes, "alerts": alerts,
            "sensors": {k: {"missing": health_an.missing(fr.env, k)} for k in health_an.ENV_KEYS},
            "real_env": fr.real_env}


@router.get("/summary")
def summary(c=Depends(ctx), dummy: str | None = DummyQ) -> dict[str, Any]:
    fr = c.frames(dummy)
    roster = c.roster(fr)
    cfg = c.store.get()
    nodes, alerts = health_an.nodes_and_alerts(fr, roster, cfg)
    return {**base_meta(fr),
            "sources": {t: ("dummy" if t in fr.fake else ("real" if n else "none"))
                        for t, n in (("env", len(fr.env)), ("soil", len(fr.soil)), ("pump", len(fr.pump)), ("growth", len(fr.grow)))},
            "pots": [{"id": p, "treat": roster.treat.get(p), "real": p in fr.real_pots} for p in roster.pots],
            "groups": roster.groups, "ncol": roster.ncol,
            "conflicts": [{"pot": p, "sources": v} for p, v in sorted(roster.conflicts.items())],
            "unknown_labels": roster.unknown, "suggested_sql": roster.suggested_sql(),
            "env": health_an.env_summary(fr), "nodes": nodes, "alerts": alerts,
            "validity": soil_an.validity(fr, roster, cfg),
            "run_started": cfg.run_started, "tz": cfg.tz, "real_env": fr.real_env,
            "capture": {"driver": c.camera.driver or c.camera.probe_driver()},
            "led": c.led.status()}


@router.get("/env")
def env(c=Depends(ctx), dummy: str | None = DummyQ, bucket: str = "auto", points: int = 600,
        frm: str | None = Query(None, alias="from"), to: str | None = None) -> dict[str, Any]:
    fr = c.frames(dummy)
    df, a, b = _window(fr.env, frm, to)
    bs = _bucket_s(bucket, a, b, points)
    cols = ["temp", "hum", "press", "vpd", "lux", "co2"]
    r = resample_columns(df, cols, bs)
    series: dict[str, Any] = {"ts": [iso_utc(t.to_pydatetime()) for t in r.ts]} if len(r) else {"ts": []}
    for col in cols:
        series[col] = [None if pd.isna(v) else round(float(v), 3) for v in r[col]] if len(r) and col in r.columns else []
    if len(r) and "n" in r.columns:
        series["n"] = [int(x) for x in r["n"]]
    summ = health_an.env_summary(fr, spark_points=0)
    return {**base_meta(fr), "bucket": bs, "series": series,
            "current": {k: summ[k]["value"] for k in summ},
            "delta_24h": {k: summ[k]["delta_1d"] for k in summ},
            "missing": {k: summ[k]["missing"] for k in summ}}


@router.get("/soil")
def soil(c=Depends(ctx), dummy: str | None = DummyQ, bucket: str = "auto", points: int = 600,
         pots: str | None = None, basis: str = "pct",
         frm: str | None = Query(None, alias="from"), to: str | None = None) -> dict[str, Any]:
    fr = c.frames(dummy)
    roster = c.roster(fr)
    cfg = c.store.get()
    df, a, b = _window(fr.soil, frm, to)
    bs = _bucket_s(bucket, a, b, points)
    fr2 = fr.__class__(**{**fr.__dict__, "soil": df})
    want = [p.strip() for p in pots.split(",")] if pots else None
    out = soil_an.soil_series(fr2, roster, cfg, bs, want, basis)
    return {**base_meta(fr), "bucket": bs, "groups": roster.groups, **out}


@router.get("/pump")
def pump(c=Depends(ctx), dummy: str | None = DummyQ, limit: int = 200,
         frm: str | None = Query(None, alias="from"), to: str | None = None) -> dict[str, Any]:
    fr = c.frames(dummy)
    df, _, _ = _window(fr.pump, frm, to)
    df = df.sort_values("ts", ascending=False).head(limit) if len(df) else df
    rows = []
    for r in df.to_dict("records"):
        r["ts"] = iso_utc(r["ts"].to_pydatetime())
        rows.append({k: (None if (isinstance(v, float) and pd.isna(v)) else v) for k, v in r.items()})
    return {**base_meta(fr), "rows": rows}


@router.get("/pump/recent")
def pump_recent(c=Depends(ctx), dummy: str | None = DummyQ, n: int = 5) -> dict[str, Any]:
    fr = c.frames(dummy)
    return {**base_meta(fr), **irr_an.recent(fr, c.roster(fr), n)}


@router.get("/growth")
def growth(c=Depends(ctx), dummy: str | None = DummyQ, phase: str = "all", pots: str | None = None,
           contour: int = 0, frm: str | None = Query(None, alias="from"), to: str | None = None) -> dict[str, Any]:
    fr = c.frames(dummy)
    df, _, _ = _window(fr.grow, frm, to)
    if phase in ("dawn", "pm") and len(df) and "phase" in df.columns:
        df = df[df.phase == phase]
    if pots and len(df):
        df = df[df.plant_id.isin([p.strip() for p in pots.split(",")])]
    rows = []
    for r in df.to_dict("records"):
        r["ts"] = iso_utc(r["ts"].to_pydatetime())
        if not contour:
            r.pop("contour", None)
        rows.append({k: (None if (isinstance(v, float) and pd.isna(v)) else v) for k, v in r.items()})
    return {**base_meta(fr), "rows": rows}


# ---- analytics ---------------------------------------------------------------
an = APIRouter(prefix="/api/analytics", tags=["analytics"])


@an.get("/validity")
def validity(c=Depends(ctx), dummy: str | None = DummyQ):
    fr = c.frames(dummy)
    return {**base_meta(fr), **soil_an.validity(fr, c.roster(fr), c.store.get())}


@an.get("/histogram")
def histogram(c=Depends(ctx), dummy: str | None = DummyQ, bins: int | None = None):
    fr = c.frames(dummy)
    return {**base_meta(fr), **soil_an.histogram(fr, c.roster(fr), c.store.get(), bins)}


@an.get("/alignment-trend")
def alignment_trend(c=Depends(ctx), dummy: str | None = DummyQ):
    fr = c.frames(dummy)
    return {**base_meta(fr), **soil_an.alignment_trend(fr, c.roster(fr), c.store.get())}


@an.get("/reference")
def reference(c=Depends(ctx), dummy: str | None = DummyQ):
    fr = c.frames(dummy)
    return {**base_meta(fr), **soil_an.reference(fr)}


@an.get("/droop")
def droop(c=Depends(ctx), dummy: str | None = DummyQ):
    fr = c.frames(dummy)
    return {**base_meta(fr), **growth_an.droop(fr, c.roster(fr), c.store.get())}


@an.get("/droop-timeline")
def droop_timeline(c=Depends(ctx), dummy: str | None = DummyQ, days: int = 14):
    fr = c.frames(dummy)
    return {**base_meta(fr), **growth_an.droop_timeline(fr, c.roster(fr), c.store.get(), days)}


@an.get("/canopy")
def canopy(c=Depends(ctx), dummy: str | None = DummyQ, phase: str = "dawn"):
    fr = c.frames(dummy)
    return {**base_meta(fr), **growth_an.canopy_series(fr, c.roster(fr), phase)}


@an.get("/silhouettes")
def silhouettes(c=Depends(ctx), dummy: str | None = DummyQ):
    fr = c.frames(dummy)
    return {**base_meta(fr), **growth_an.silhouettes(fr, c.roster(fr))}


@an.get("/rgr")
def rgr(c=Depends(ctx), dummy: str | None = DummyQ):
    fr = c.frames(dummy)
    return {**base_meta(fr), **growth_an.rgr(fr, c.roster(fr))}


@an.get("/water")
def water(c=Depends(ctx), dummy: str | None = DummyQ, days: int = 14):
    fr = c.frames(dummy)
    return {**base_meta(fr), **irr_an.water_summary(fr, c.roster(fr), c.store.get().tz, days)}


@an.get("/all")
def all_analytics(c=Depends(ctx), dummy: str | None = DummyQ):
    fr = c.frames(dummy)
    roster = c.roster(fr)
    cfg = c.store.get()
    nodes, alerts = health_an.nodes_and_alerts(fr, roster, cfg)
    return {**base_meta(fr), "groups": roster.groups, "pots": roster.pots,
            "health": {"nodes": nodes, "alerts": alerts, "conflicts": roster.conflicts, "unknown": roster.unknown},
            "env": health_an.env_summary(fr),
            "validity": soil_an.validity(fr, roster, cfg),
            "histogram": soil_an.histogram(fr, roster, cfg),
            "alignment": soil_an.alignment_trend(fr, roster, cfg),
            "reference": soil_an.reference(fr),
            "droop": growth_an.droop(fr, roster, cfg),
            "droop_timeline": growth_an.droop_timeline(fr, roster, cfg),
            "canopy": growth_an.canopy_series(fr, roster),
            "silhouettes": growth_an.silhouettes(fr, roster),
            "rgr": growth_an.rgr(fr, roster),
            "pump_recent": irr_an.recent(fr, roster),
            "water": irr_an.water_summary(fr, roster, cfg.tz)}
