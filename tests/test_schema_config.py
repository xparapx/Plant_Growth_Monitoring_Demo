import json
import sqlite3

import pytest

from plantsvc.config_check import check
from plantsvc.config_model import Config, migrate
from plantsvc.config_store import ConfigError, ConfigStore
from plantsvc.schema import INDEXES, TABLES, WANT, ensure_schema, table_columns


def test_schema_idempotent_and_migrates_old_tables(tmp_path):
    conn = sqlite3.connect(tmp_path / "plant.db")
    # an old-shape soil table without `raw`, growth without contour/ok
    conn.execute("CREATE TABLE soil(id INTEGER PRIMARY KEY, ts TEXT, node TEXT, plant_id TEXT, treat TEXT, pct REAL, n INTEGER)")
    conn.execute("CREATE TABLE growth(id INTEGER PRIMARY KEY, ts TEXT, plant_id TEXT, treat TEXT, phase TEXT, area_cm2 REAL, area_px INTEGER, img_file TEXT)")
    added = ensure_schema(conn, log=None)
    assert "soil.raw" in added and "growth.contour" in added and "growth.ok" in added
    for t in TABLES:
        assert table_columns(conn, t)
    for tbl, cols in WANT.items():
        have = table_columns(conn, tbl)
        for name, _ in cols:
            assert name in have
    assert ensure_schema(conn, log=None) == []          # second run adds nothing
    idx = {r[1] for r in conn.execute("PRAGMA index_list(soil)")}
    assert any(n.startswith("idx_soil") for n in idx)
    assert len(INDEXES) == 5


def test_migrate_drops_dead_keys_and_normalises():
    legacy = json.load(open("hub/config.example.json", encoding="utf-8"))
    legacy.update({"marker_mm": 50.0, "ref_marker": [], "tz": "Mars/Olympus", "treat_mode": "weird"})
    legacy["qc"]["px_per_cm_tol"] = 0.03
    legacy["rois"] = [{"plant_id": "p1", "treat": None, "x": 1, "y": 2, "w": 3, "h": 4, "_new": (5, 6)}, "garbage"]
    data, warns = migrate(legacy)
    assert "marker_mm" not in data and "ref_marker" not in data and "px_per_cm_tol" not in data["qc"]
    assert data["tz"] == "Asia/Seoul" and data["treat_mode"] == ""
    assert data["rois"] == [{"plant_id": "p1", "treat": "", "x": 1, "y": 2, "w": 3, "h": 4}]
    assert len(warns) >= 5
    cfg = Config.model_validate(data)
    assert cfg.led.enabled is False and cfg.led.driver == "noop"
    assert cfg.schedule.dawn == "05:50" and cfg.analysis.dummy_fill == "auto"
    assert abs(cfg.scale - 1280 / 4608) < 1e-9
    assert cfg.bands.band_pct()["fluct"][0] < cfg.bands.band_pct()["fluct"][1]


def test_store_seeds_saves_atomically_and_reloads(paths):
    s = ConfigStore(paths.config, example=paths.example_config)
    cfg = s.load()
    assert paths.config.exists() and cfg.version == 2
    assert not list(paths.data_dir.glob("*.tmp"))
    s.update(lambda c: setattr(c.layout, "pot_cm", 12.5))
    assert json.loads(paths.config.read_text(encoding="utf-8"))["layout"]["pot_cm"] == 12.5
    # an external writer (legacy CLI) changes the file -> get() sees it
    raw = json.loads(paths.config.read_text(encoding="utf-8"))
    raw["layout"]["pot_cm"] = 9
    import os
    import time
    time.sleep(0.01)
    paths.config.write_text(json.dumps(raw), encoding="utf-8")
    os.utime(paths.config, None)
    assert s.get().layout.pot_cm == 9
    with pytest.raises(ConfigError):
        s.replace({"capture": {"size": "not-a-size"}})
    with pytest.raises(ConfigError):
        s.replace({"schedule": {"dawn": "25:99"}})


def test_check_flags_geometry_and_labels(store):
    cfg = store.get()
    cfg.qc.px_per_cm_ref = 30.0
    cfg.rois = [type(cfg.rois)()] if False else []
    from plantsvc.config_model import Roi
    cfg.rois = [Roi(plant_id="p1", treat="stable", x=0, y=0, w=1000, h=1000),
                Roi(plant_id="p2", treat="A", x=500, y=500, w=1000, h=1000),
                Roi(plant_id="p3", treat="fluct", x=4000, y=2000, w=1000, h=1000)]
    rep = check(cfg)
    joined = " ".join(rep["bad"])
    assert "겹칩니다" in joined and "벗어납니다" in joined and '"A"' in joined
    assert rep["ok"] is False
    cfg.rois = [Roi(plant_id="p1", treat="stable", x=0, y=0, w=800, h=800),
                Roi(plant_id="p2", treat="fluct", x=1000, y=0, w=800, h=800)]
    rep = check(cfg)
    assert rep["ok"] is True and rep["lines"]
