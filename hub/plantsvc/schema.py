"""SQLite schema for plant.db.

Shared by `hub/run_collector.py` (the ONLY writer) and plantsvc (read-only
consumers, `plantsvc seed`, tests).  Column comments are kept verbatim from the
original collector - they are the data dictionary.

CREATE TABLE IF NOT EXISTS never adds columns to an existing table, so wanted
columns are listed in WANT and ALTERed in (old rows get NULL).
"""

from __future__ import annotations

import sqlite3

TABLES = ("readings", "soil", "pump_log", "growth")

DDL: dict[str, str] = {
    # environment = the whole grow box.  ONE node.  no soil here.
    "readings": """
CREATE TABLE IF NOT EXISTS readings(
  id   INTEGER PRIMARY KEY AUTOINCREMENT,
  ts   TEXT DEFAULT CURRENT_TIMESTAMP,
  node TEXT,
  temp  REAL,     -- C    (BME688 = representative)
  hum   REAL,     -- %    (BME688)
  press REAL,     -- hPa  (BME688)
  vpd   REAL,     -- kPa  <- drives transpiration => drying rate => cycle period
  lux   REAL,     -- lx   (proxy only, NOT PAR -- see FAQ)
  co2   REAL,     -- ppm  (SCD41)
  n     INTEGER   -- samples in bucket (quality indicator)
)""",
    # soil = per pot.  one watering node per plant.
    "soil": """
CREATE TABLE IF NOT EXISTS soil(
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  ts       TEXT DEFAULT CURRENT_TIMESTAMP,
  node     TEXT,
  plant_id TEXT,   -- p1..p6
  treat    TEXT,   -- 'stable' | 'fluct'  <- witness only; config.json is the source
  raw      REAL,   -- ADC counts as the sensor reports them.  THE value to keep.
  pct      REAL,   -- convenience only.  do not compare across nodes/dates.
  n        INTEGER
)""",
    "pump_log": """
CREATE TABLE IF NOT EXISTS pump_log(
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          TEXT DEFAULT CURRENT_TIMESTAMP,
  node        TEXT,
  plant_id    TEXT,
  treat       TEXT,
  dur_ms      INTEGER,
  soil_before REAL,   -- derived pct -- see the note on soil.raw
  soil_after  REAL,
  raw_before  INTEGER,
  raw_after   INTEGER,
  shots       INTEGER,-- doses used in this cycle (MAX_SHOTS => verify fail)
  reason      TEXT    -- filled | dosed | no rise | verify fail | manual
)""",
    "growth": """
CREATE TABLE IF NOT EXISTS growth(
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  ts        TEXT DEFAULT CURRENT_TIMESTAMP,
  plant_id  TEXT,
  treat     TEXT,
  phase     TEXT,     -- 'dawn' | 'pm'  <- RGR uses dawn ONLY; pm is for droop
  area_cm2  REAL,     -- projected canopy area (NOT leaf area -- see FAQ)
  area_px   INTEGER,
  px_per_cm REAL,     -- scale at capture (traceability + rig-moved alarm)
  img_file  TEXT,     -- raw/<file> -- links this row to the evidence image
  contour   TEXT,     -- JSON [[dx,dy],...] outline in px, centred on centroid
  ok        INTEGER
)""",
}

WANT: dict[str, list[tuple[str, str]]] = {
    "soil": [("raw", "REAL")],
    "pump_log": [("raw_before", "INTEGER"), ("raw_after", "INTEGER"), ("shots", "INTEGER")],
    "growth": [("px_per_cm", "REAL"), ("contour", "TEXT"), ("ok", "INTEGER")],
}

INDEXES: list[tuple[str, str, str]] = [
    ("idx_readings_ts", "readings", "(ts)"),
    ("idx_soil_pid_ts", "soil", "(plant_id, ts)"),
    ("idx_soil_ts", "soil", "(ts)"),
    ("idx_pump_ts", "pump_log", "(ts)"),
    ("idx_growth_pid_phase_ts", "growth", "(plant_id, phase, ts)"),
]

# The columns the collector extracts from each MQTT payload (order matters for INSERT).
INSERT_COLS: dict[str, list[str]] = {
    "readings": ["node", "temp", "hum", "press", "vpd", "lux", "co2", "n"],
    "soil": ["node", "plant_id", "treat", "raw", "pct", "n"],
    "pump_log": ["node", "plant_id", "treat", "dur_ms", "soil_before", "soil_after",
                 "raw_before", "raw_after", "shots", "reason"],
    "growth": ["plant_id", "treat", "phase", "area_cm2", "area_px", "px_per_cm",
               "img_file", "contour", "ok"],
}


def ensure_schema(conn: sqlite3.Connection, *, log=print) -> list[str]:
    """Create tables, add missing WANT columns, create indexes.  Idempotent.
    Returns the list of '<table>.<column>' that were added."""
    for sql in DDL.values():
        conn.execute(sql)
    added: list[str] = []
    for tbl, cols in WANT.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({tbl})")}
        for name, typ in cols:
            if name not in have:
                conn.execute(f"ALTER TABLE {tbl} ADD COLUMN {name} {typ}")
                added.append(f"{tbl}.{name}")
                if log:
                    log(f"[migrate] {tbl}.{name} {typ} added")
    for name, tbl, cols in INDEXES:
        conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {tbl}{cols}")
    conn.commit()
    return added


def configure_writer(conn: sqlite3.Connection) -> None:
    """WAL so read-only readers (plantsvc) never block the collector, and vice versa."""
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.DatabaseError:
        pass
    conn.execute("PRAGMA busy_timeout=3000")
    conn.execute("PRAGMA synchronous=NORMAL")


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
