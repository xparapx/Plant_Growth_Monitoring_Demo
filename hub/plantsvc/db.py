"""Read-only access to plant.db and the dummy-fill policy.

plantsvc never writes plant.db (run_collector.py is the single writer).  The
four frames the dashboard always used are loaded here, in UTC-aware pandas
timestamps, with the same dummy-fill behaviour as dashboard.py: a table that is
empty is filled with synthetic rows and *named* in `Frames.fake`, so every
response can carry a DUMMY DATA badge for exactly those sections.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from .config_model import Config
from .schema import TABLES
from .settings import Paths

TS_COLS = ("ts",)


def ro_connect(db_path: str | Path) -> sqlite3.Connection | None:
    """Read-only connection, or None when the file does not exist yet."""
    p = Path(db_path)
    if not p.exists():
        return None
    try:
        conn = sqlite3.connect(p.resolve().as_uri() + "?mode=ro", uri=True, timeout=2.0,
                               check_same_thread=False)
        conn.execute("SELECT 1")
    except sqlite3.Error:
        conn = sqlite3.connect(str(p), timeout=2.0, check_same_thread=False)
        conn.execute("PRAGMA query_only=1")
    conn.execute("PRAGMA busy_timeout=2000")
    return conn


def _read(conn: sqlite3.Connection | None, sql: str, params: tuple = ()) -> pd.DataFrame:
    if conn is None:
        return pd.DataFrame()
    try:
        df = pd.read_sql_query(sql, conn, params=params)
    except Exception:
        return pd.DataFrame()
    if "ts" in df.columns and len(df):
        df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
        df = df.dropna(subset=["ts"])
    return df


def table_counts(conn: sqlite3.Connection | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for t in TABLES:
        if conn is None:
            out[t] = {"rows": 0, "max_ts": None}
            continue
        try:
            n, mx = conn.execute(f"SELECT COUNT(*), MAX(ts) FROM {t}").fetchone()
            out[t] = {"rows": int(n), "max_ts": mx}
        except sqlite3.Error:
            out[t] = {"rows": 0, "max_ts": None}
    return out


@dataclass
class Frames:
    env: pd.DataFrame
    soil: pd.DataFrame
    pump: pd.DataFrame
    grow: pd.DataFrame
    fake: set[str] = field(default_factory=set)      # subset of {"env","soil","pump","growth"}
    real_pots: set[str] = field(default_factory=set)
    real_env: bool = False
    now: pd.Timestamp | None = None                   # max ts over all four (dummy included)
    now_real: pd.Timestamp | None = None
    tz: str = "Asia/Seoul"

    @property
    def dummy(self) -> list[str]:
        return sorted(self.fake)


def _max_ts(*dfs: pd.DataFrame) -> pd.Timestamp | None:
    vals = [d.ts.max() for d in dfs if len(d) and "ts" in d.columns]
    vals = [v for v in vals if pd.notna(v)]
    return max(vals) if vals else None


def load_frames(paths: Paths, cfg: Config, *, dummy: str | None = None,
                soil_days: int | None = None, env_days: int | None = None,
                pump_limit: int | None = None) -> Frames:
    """The dashboard's four queries + dummy fill.  `dummy` overrides cfg.analysis.dummy_fill."""
    from .analytics import dummy as dummy_mod
    from .analytics.roster import roster_of

    mode = dummy or cfg.analysis.dummy_fill
    soil_days = soil_days or cfg.analysis.soil_days
    pump_limit = pump_limit or cfg.analysis.pump_limit
    conn = ro_connect(paths.db)
    try:
        env_sql = "SELECT * FROM readings"
        if env_days:
            env_sql += f" WHERE ts > datetime('now','-{int(env_days)} day')"
        env = _read(conn, env_sql + " ORDER BY ts")
        soil = _read(conn, f"SELECT * FROM soil WHERE ts > datetime('now','-{int(soil_days)} day') ORDER BY ts")
        pump = _read(conn, f"SELECT * FROM pump_log ORDER BY ts DESC LIMIT {int(pump_limit)}")
        grow = _read(conn, "SELECT * FROM growth WHERE ok=1 ORDER BY ts")
    finally:
        if conn is not None:
            conn.close()

    real_pots = set(roster_of(soil, grow))
    real_env = not env.empty
    fake: set[str] = set()
    now_real = _max_ts(env, soil, pump, grow)

    if mode == "on":
        env, soil, pump, grow = pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    if mode in ("auto", "on"):
        need = [t for t, d in (("soil", soil), ("pump", pump), ("growth", grow), ("env", env)) if d.empty]
        if need:
            s2, p2, g2, e2 = dummy_mod.synth(cfg, roster_of(soil, grow) or None)
            if soil.empty:
                soil, _ = s2, fake.add("soil")
            if pump.empty:
                pump, _ = p2, fake.add("pump")
            if grow.empty:
                grow, _ = g2, fake.add("growth")
            if env.empty:
                env, _ = e2, fake.add("env")

    return Frames(env=env, soil=soil, pump=pump, grow=grow, fake=fake, real_pots=real_pots,
                  real_env=real_env, now=_max_ts(env, soil, pump, grow), now_real=now_real,
                  tz=cfg.tz)


class FrameCache:
    """Tiny TTL cache so a burst of analytics requests hits SQLite once."""

    def __init__(self, ttl_s: float = 15.0):
        self.ttl = ttl_s
        self._lock = threading.Lock()
        self._items: dict[tuple, tuple[float, Frames]] = {}
        self.version = 0

    def invalidate(self) -> None:
        with self._lock:
            self.version += 1
            self._items.clear()

    def get(self, key: tuple, build) -> Frames:
        now = time.monotonic()
        with self._lock:
            hit = self._items.get(key)
            if hit and now - hit[0] < self.ttl:
                return hit[1]
        fr = build()
        with self._lock:
            self._items[key] = (now, fr)
        return fr


# ---- bucketing ---------------------------------------------------------------
BUCKETS = {"raw": 0, "5m": 300, "15m": 900, "1h": 3600, "6h": 21600, "1d": 86400}


def auto_bucket(span_s: float, points: int = 600) -> int:
    for b in (300, 900, 3600, 10800, 21600, 86400):
        if span_s / b <= points:
            return b
    return 86400


def resample_columns(df: pd.DataFrame, cols: list[str], bucket_s: int,
                     by: str | None = None) -> pd.DataFrame:
    """Mean per bucket (plus count n).  bucket_s == 0 returns the rows as they are."""
    if df.empty:
        return df
    d = df.copy()
    if bucket_s <= 0:
        keep = ["ts"] + ([by] if by else []) + [c for c in cols if c in d.columns]
        return d[keep].sort_values("ts")
    epoch = (d["ts"].astype("int64") // 10**9)
    d["b"] = (epoch // bucket_s) * bucket_s
    agg = {c: "mean" for c in cols if c in d.columns}
    keys = ["b"] + ([by] if by else [])
    g = d.groupby(keys).agg(**{c: (c, "mean") for c in agg}, n=("ts", "size")).reset_index()
    g["ts"] = pd.to_datetime(g.pop("b"), unit="s", utc=True)
    return g.sort_values(["ts"] + ([by] if by else []))
