"""Synthetic data for layout preview - port of dashboard.synth().

Rules that make it safe to show: every synthetic row carries node='dummy',
every response lists which tables are synthetic, and synthetic faults never
raise alerts (health.py checks `real`).  If a roster is given the fake pots
follow the REAL pot ids and treatments so real canopy rows and fake soil rows
line up on the same pot.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ..config_model import Config


def _blob(R: float, seed: int, k: int = 9) -> str:
    r = np.random.default_rng(seed)
    ph, ph2 = r.uniform(0, 6.3, 2)
    a = np.arange(0, 6.2832, .1)
    rad = R * (1 + .16 * np.sin(k * a + ph) + .09 * np.sin(2 * k * a + ph2))
    return json.dumps([[round(float(rad[i] * np.cos(a[i])), 1),
                        round(float(rad[i] * np.sin(a[i])), 1)] for i in range(len(a))])


def synth(cfg: Config, roster: dict[str, str] | None = None, days: int = 7, step_min: int = 30,
          seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """-> (soil, pump, growth, env) frames with UTC-aware ts, node='dummy'."""
    rng = np.random.default_rng(seed)
    band = cfg.bands.band_pct()
    n = days * 24 * 60 // step_min
    t0 = pd.Timestamp.now(tz="UTC").floor("h") - pd.Timedelta(minutes=step_min * (n - 1))
    ts = [t0 + pd.Timedelta(minutes=step_min * i) for i in range(n)]
    local_hours = [t.tz_convert(cfg.tz).hour for t in ts]

    if roster:
        pots = [(pid, tr, *band.get(tr, (30.0, 55.0))) for pid, tr in sorted(roster.items())]
    else:
        pots = [(f"p{i}", t, *band[t]) for i, t in enumerate(["stable"] * 3 + ["fluct"] * 3, 1)]

    soil, pump = [], []
    for k, (pid, tr, on, off) in enumerate(pots):
        v, filling = off - rng.uniform(0, 3), False
        for i in range(n):
            hh = local_hours[i]
            rate = (0.55 if 7 <= hh < 19 else 0.12) * (1 + 0.10 * (k % 3 - 1))
            if filling:
                v += 4.5
                if v >= off:
                    v, filling = off, False
            else:
                v -= rate * (step_min / 30) * rng.uniform(.85, 1.15)
                if v <= on:
                    filling = True
                    pump.append(dict(ts=ts[i], node="dummy", plant_id=pid, treat=tr,
                                     dur_ms=int(rng.uniform(2400, 3600)),
                                     soil_before=round(v, 1), soil_after=float(off),
                                     raw_before=None, raw_after=None, shots=1, reason="filled"))
            soil.append(dict(ts=ts[i], node="dummy", plant_id=pid, treat=tr, raw=None,
                             pct=round(v + rng.normal(0, .25), 2), n=30))
    soil_df = pd.DataFrame(soil)

    ids = [x[0] for x in pots]
    if len(ids) >= 5:                                   # stuck-sensor demo
        m = (soil_df.plant_id == ids[4]) & (soil_df.ts >= ts[-12])
        soil_df.loc[m, "pct"] = float(soil_df.loc[m, "pct"].iloc[0])
    if len(ids) >= 2:                                   # verify-fail demo
        pump.append(dict(ts=ts[-40], node="dummy", plant_id=ids[1], treat=pots[1][1],
                         dur_ms=3000, soil_before=37.8, soil_after=38.0, raw_before=None,
                         raw_after=None, shots=6, reason="verify fail"))
    pump_df = pd.DataFrame(pump)
    if len(pump_df):
        pump_df = pump_df.sort_values("ts", ascending=False).reset_index(drop=True)

    grow = []
    day0 = t0.tz_convert(cfg.tz).normalize()
    for d in range(days):
        for k, (pid, tr, *_) in enumerate(pots):
            base = (11.5 * np.exp(.145 * d) if tr == "stable" else 11.3 * np.exp(.131 * d))
            base *= 1 + rng.normal(0, .05)
            droop = rng.uniform(2, 5) if tr == "stable" else rng.uniform(9, 17)
            for phase, mult, hour in (("dawn", 1.0, 6), ("pm", 1 - droop / 100, 15)):
                area = base * mult
                grow.append(dict(ts=(day0 + pd.Timedelta(days=d, hours=hour)).tz_convert("UTC"),
                                 plant_id=pid, treat=tr, phase=phase,
                                 area_cm2=round(area, 2), area_px=int(area * 900),
                                 px_per_cm=30.0, img_file="", ok=1,
                                 contour=_blob(30 * np.sqrt(area / 11.5), k * 13 + 3)))
    grow_df = pd.DataFrame(grow)

    hrs = np.array(local_hours)
    day = (hrs >= 7) & (hrs < 19)
    i = np.arange(n)
    temp = 21 + 4 * np.sin(i / (24 * 60 / step_min) * 2 * np.pi) + rng.normal(0, .2, n)
    hum = np.clip(60 - (temp - 21) * 2.5 + rng.normal(0, 1, n), 35, 90)
    svp = 0.6108 * np.exp(17.27 * temp / (temp + 237.3))
    vpd = svp * (1 - hum / 100)
    env_df = pd.DataFrame(dict(ts=ts, node="dummy", temp=np.round(temp, 2), hum=np.round(hum, 1),
                               press=1013.0 + rng.normal(0, .5, n).round(1), vpd=np.round(vpd, 3),
                               lux=np.where(day, 8000 + rng.normal(0, 300, n), 20).round(0),
                               co2=np.where(day, 520, 640) + rng.normal(0, 15, n).round(0), n=30))
    return soil_df, pump_df, grow_df, env_df
