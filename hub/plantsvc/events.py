"""events.db - the service's own writable store (plant.db stays read-only here).

  jobs    one row per capture run (CLI or API), updated as the routine advances
  events  led on/off, capture steps, config saves, camera open/close, mqtt state
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .timeutil import iso_utc, now_utc

DDL = [
    """CREATE TABLE IF NOT EXISTS jobs(
        id TEXT PRIMARY KEY, phase TEXT, trigger TEXT, state TEXT, step TEXT,
        started_at TEXT, finished_at TEXT, img_file TEXT, n_rows INTEGER, ok_rows INTEGER,
        published INTEGER, error TEXT, data_json TEXT)""",
    """CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, type TEXT, data_json TEXT)""",
    "CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_started ON jobs(started_at)",
]


class EventStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False, timeout=5.0)
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
            pass
        self.conn.execute("PRAGMA busy_timeout=3000")
        for sql in DDL:
            self.conn.execute(sql)
        self.conn.commit()

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    # ---- events ------------------------------------------------------------
    def add(self, type_: str, data: dict[str, Any] | None = None) -> None:
        with self._lock:
            self.conn.execute("INSERT INTO events(ts,type,data_json) VALUES(?,?,?)",
                              (iso_utc(now_utc()), type_, json.dumps(data or {}, ensure_ascii=False)))
            self.conn.commit()

    def events(self, type_: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            if type_:
                rows = self.conn.execute(
                    "SELECT id,ts,type,data_json FROM events WHERE type LIKE ? ORDER BY id DESC LIMIT ?",
                    (f"{type_}%", int(limit))).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT id,ts,type,data_json FROM events ORDER BY id DESC LIMIT ?",
                    (int(limit),)).fetchall()
        return [{"id": r[0], "ts": r[1], "type": r[2], "data": json.loads(r[3] or "{}")} for r in rows]

    # ---- jobs --------------------------------------------------------------
    def upsert_job(self, job: dict[str, Any]) -> None:
        cols = ("id", "phase", "trigger", "state", "step", "started_at", "finished_at",
                "img_file", "n_rows", "ok_rows", "published", "error")
        vals = [job.get(c) for c in cols]
        extra = {k: v for k, v in job.items() if k not in cols}
        with self._lock:
            self.conn.execute(
                f"INSERT OR REPLACE INTO jobs({','.join(cols)},data_json) VALUES({','.join('?' * len(cols))},?)",
                (*vals, json.dumps(extra, ensure_ascii=False, default=str)))
            self.conn.commit()

    def _row(self, r) -> dict[str, Any]:
        cols = ("id", "phase", "trigger", "state", "step", "started_at", "finished_at",
                "img_file", "n_rows", "ok_rows", "published", "error")
        d = dict(zip(cols, r[:len(cols)], strict=True))
        d.update(json.loads(r[len(cols)] or "{}"))
        d["published"] = bool(d.get("published"))
        return d

    def jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT id,phase,trigger,state,step,started_at,finished_at,img_file,n_rows,ok_rows,"
                "published,error,data_json FROM jobs ORDER BY started_at DESC LIMIT ?",
                (int(limit),)).fetchall()
        return [self._row(r) for r in rows]

    def job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            r = self.conn.execute(
                "SELECT id,phase,trigger,state,step,started_at,finished_at,img_file,n_rows,ok_rows,"
                "published,error,data_json FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._row(r) if r else None

    def running_job(self) -> dict[str, Any] | None:
        with self._lock:
            r = self.conn.execute(
                "SELECT id,phase,trigger,state,step,started_at,finished_at,img_file,n_rows,ok_rows,"
                "published,error,data_json FROM jobs WHERE state IN ('queued','running') "
                "ORDER BY started_at DESC LIMIT 1").fetchone()
        return self._row(r) if r else None
