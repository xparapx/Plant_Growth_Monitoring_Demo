import json

import numpy as np
import pandas as pd

from plantsvc.analytics import growth as ga
from plantsvc.analytics import health as ha
from plantsvc.analytics import irrigation as ia
from plantsvc.analytics import soil as sa
from plantsvc.analytics.dummy import synth
from plantsvc.analytics.roster import build_roster
from plantsvc.db import Frames, auto_bucket, load_frames, resample_columns


def frames_from_synth(cfg, **kw) -> Frames:
    soil, pump, grow, env = synth(cfg, None, days=6)
    fr = Frames(env=env, soil=soil, pump=pump, grow=grow, fake=set(), real_pots=set(soil.plant_id.unique()),
                real_env=True, now=max(env.ts.max(), soil.ts.max(), grow.ts.max()), now_real=None, tz=cfg.tz)
    for k, v in kw.items():
        setattr(fr, k, v)
    return fr


def test_dummy_fill_marks_tables_and_switches_per_table(paths, store):
    cfg = store.get()
    fr = load_frames(paths, cfg)                       # no DB at all -> everything synthetic
    assert fr.dummy == ["env", "growth", "pump", "soil"] and not fr.real_pots
    fr_off = load_frames(paths, cfg, dummy="off")
    assert fr_off.soil.empty and fr_off.dummy == []


def test_validity_histogram_alignment(store):
    cfg = store.get()
    fr = frames_from_synth(cfg)
    roster = build_roster(fr.soil, fr.grow)
    assert roster.groups.keys() == {"stable", "fluct"} and roster.ncol == 3
    v = sa.validity(fr, roster, cfg)
    assert v["enough_groups"] and v["ratio"] > 1.0 and v["dmu"] is not None
    h = sa.histogram(fr, roster, cfg)
    assert len(h["edges"]) == cfg.analysis.hist_bins + 1
    for g in h["groups"].values():
        assert abs(sum(g["prob"]) - 1.0) < 1e-3          # probabilities are rounded to 5 dp
    assert h["e_w"] is not None and h["quantiles"]["p05"] < h["quantiles"]["p95"]
    a = sa.alignment_trend(fr, roster, cfg)
    assert a["weeks"] and set(a["groups"]) == {"stable", "fluct"}
    ss = sa.soil_series(fr, roster, cfg, 900)
    assert len(ss["pots"]) == 6 and ss["yrange"][0] < ss["yrange"][1] and "stable" in ss["band_pct"]


def test_rgr_exact_exponential_and_cohens_d(store):
    rows = []
    t0 = pd.Timestamp("2026-08-01T06:00:00Z")
    for pid, tr, k in (("p1", "stable", 0.15), ("p2", "stable", 0.16), ("p3", "fluct", 0.10), ("p4", "fluct", 0.11)):
        for d in range(6):
            rows.append(dict(ts=t0 + pd.Timedelta(days=d), plant_id=pid, treat=tr, phase="dawn",
                             area_cm2=10 * np.exp(k * d), area_px=1000, contour="[[0,0]]", ok=1))
    grow = pd.DataFrame(rows)
    fr = Frames(env=pd.DataFrame(), soil=pd.DataFrame(), pump=pd.DataFrame(), grow=grow, real_pots={"p1", "p2", "p3", "p4"})
    roster = build_roster(fr.soil, fr.grow)
    r = ga.rgr(fr, roster)
    by = {p["pot"]: p for p in r["pots"]}
    assert abs(by["p1"]["rgr"] - 0.15) < 1e-6 and by["p1"]["r2"] > 0.9999
    assert r["groups"]["stable"]["n"] == 2 and r["comparable"]
    assert r["cohens_d"] is not None and r["effect"] == "large"


def test_droop_silhouettes_canopy_water(store):
    cfg = store.get()
    fr = frames_from_synth(cfg)
    roster = build_roster(fr.soil, fr.grow)
    d = ga.droop(fr, roster, cfg)
    assert d["has_both_phases"] and len(d["rows"]) == 6 and not d["missing"]
    assert all(2 <= r["droop_pct"] <= 18 for r in d["rows"])
    tl = ga.droop_timeline(fr, roster, cfg)
    assert tl["days"] and len(tl["pots"]) == 6
    s = ga.silhouettes(fr, roster)
    assert len(s["pots"]) == 6 and not s["not_enough"]
    assert len(s["pots"][0]["new"]["contour"]) > 10 and s["pots"][0]["gap_d"] >= 1
    c = ga.canopy_series(fr, roster)
    assert len(c["pots"]) == 6 and len(c["pots"][0]["ts"]) == 6
    w = ia.water_summary(fr, roster, cfg.tz)
    assert set(w["groups"]) == {"stable", "fluct"} and w["groups"]["fluct"]["total_ml"] > 0
    rec = ia.recent(fr, roster, 5)
    assert len(rec["rows"]) == 5 and rec["rows"][0]["pump_s"] > 0


def test_health_rules(store):
    cfg = store.get()
    fr = frames_from_synth(cfg)
    roster = build_roster(fr.soil, fr.grow)
    nodes, alerts = ha.nodes_and_alerts(fr, roster, cfg)
    by = {n["name"]: n for n in nodes}
    assert by["P5"]["stuck"] and by["P5"]["state"] == "bad"              # synth stuck sensor on pot 5
    codes = {a["code"] for a in alerts}
    assert "stuck_sensor" in codes and "verify_fail" in codes              # 'verify fail' with a SPACE is detected
    assert by["ENV"]["state"] == "ok" and by["CAM"]["real"]
    # a dummy pot never alerts
    fr2 = frames_from_synth(cfg, real_pots=set(), real_env=False, fake={"soil", "pump", "growth", "env"})
    nodes2, alerts2 = ha.nodes_and_alerts(fr2, roster, cfg)
    assert all(n["state"] == "off" for n in nodes2) and not [a for a in alerts2 if a["code"] in ("stuck_sensor", "verify_fail")]
    # sensor missing: temp & hum both ~0 for the last 12 rows
    env = fr.env.copy()
    env.loc[env.index[-12:], ["temp", "hum"]] = 0.0
    fr3 = frames_from_synth(cfg, env=env)
    assert ha.missing(fr3.env, "temp") and ha.missing(fr3.env, "vpd") and not ha.missing(fr3.env, "co2")
    es = ha.env_summary(fr3)
    assert es["temp"]["missing"] and es["temp"]["value"] is None and es["co2"]["value"] is not None


def test_roster_conflicts_and_unknown_labels(store):
    cfg = store.get()
    fr = frames_from_synth(cfg)
    soil = fr.soil.copy()
    soil.loc[soil.plant_id == "p2", "treat"] = "fluct"         # firmware says fluct, config(growth) says stable
    soil.loc[soil.plant_id == "p6", "treat"] = "A"             # leftover MQTT test label
    grow = fr.grow[fr.grow.plant_id != "p6"]
    roster = build_roster(soil, grow)
    assert "p2" in roster.conflicts and "p2" not in roster.pots
    assert roster.unknown == ["A"] and "p6" not in roster.pots
    assert "DELETE FROM soil" in roster.suggested_sql()


def test_bucketing_matches_pandas_resample(store):
    cfg = store.get()
    fr = frames_from_synth(cfg)
    r = resample_columns(fr.env, ["temp"], 3600)
    ref = fr.env.set_index("ts").temp.resample("1h").mean().dropna()
    assert len(r) == len(ref)
    assert np.allclose(r.temp.to_numpy(), ref.to_numpy())
    assert auto_bucket(7 * 86400, 700) == 900 and auto_bucket(7 * 86400, 600) == 3600
    assert auto_bucket(42 * 86400, 600) == 10800
    assert json.dumps({"n": [int(x) for x in r["n"]]})
