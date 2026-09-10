"""Time helpers.

Storage is UTC everywhere (plant.db `ts`, growth.jsonl `t`, API JSON).  Only two
things are local: the capture file stem (audit of the wall-clock shot time) and
the dawn/pm day grouping.  Both use config.json `tz` via zoneinfo - never a
hard-coded +9h.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DB_FMT = "%Y-%m-%d %H:%M:%S"
STEM_FMT = "%Y-%m-%d_%H%M"
DEFAULT_TZ = "Asia/Seoul"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def tzinfo(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TZ)


def db_ts(dt: datetime | None = None) -> str:
    """UTC 'YYYY-MM-DD HH:MM:SS' - the format nodes and run_capture publish."""
    return (dt or now_utc()).astimezone(timezone.utc).strftime(DB_FMT)


def parse_db_ts(value) -> datetime | None:
    """Accepts DB text, ISO-8601 (with or without Z/offset), or datetime.  Returns aware UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    s = str(value).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        try:
            dt = datetime.strptime(s, DB_FMT)
        except ValueError:
            return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def iso_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_local(dt: datetime, tz: str | None) -> datetime:
    return dt.astimezone(tzinfo(tz))


def local_day(dt: datetime, tz: str | None) -> date:
    return to_local(dt, tz).date()


def local_stem(dt: datetime | None, tz: str | None) -> str:
    return to_local(dt or now_utc(), tz).strftime(STEM_FMT)


def phase_now(tz: str | None, dt: datetime | None = None) -> str:
    """Same rule as run_capture.phase_now(): before local noon -> dawn."""
    return "dawn" if to_local(dt or now_utc(), tz).hour < 12 else "pm"


def parse_hhmm(s: str) -> tuple[int, int]:
    h, m = s.strip().split(":")
    h, m = int(h), int(m)
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError(f"bad HH:MM: {s!r}")
    return h, m


def next_occurrence(hhmm: str, tz: str | None, after: datetime | None = None) -> datetime:
    """Next local wall-clock occurrence of HH:MM strictly after `after` (UTC aware)."""
    h, m = parse_hhmm(hhmm)
    base = to_local(after or now_utc(), tz)
    cand = base.replace(hour=h, minute=m, second=0, microsecond=0)
    if cand <= base:
        cand += timedelta(days=1)
    return cand.astimezone(timezone.utc)


def add_minutes(hhmm: str, minutes: int) -> str:
    h, m = parse_hhmm(hhmm)
    total = (h * 60 + m + minutes) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def seconds_between_hhmm(a: str, b: str) -> int:
    """Seconds from local time a to b on the same day (negative if b < a)."""
    ah, am = parse_hhmm(a)
    bh, bm = parse_hhmm(b)
    return (bh * 60 + bm - ah * 60 - am) * 60


def parse_systemd_ts(value: str | None, tz: str | None = None) -> str | None:
    """'Fri 2026-09-11 05:50:00 KST' (systemctl show) -> ISO-8601 UTC, or None when empty/unparseable.
    The zone abbreviation is ignored; the time is taken as the host's local time (config tz)."""
    if not value:
        return None
    parts = value.strip().split()
    for i in range(len(parts) - 1):
        try:
            dt = datetime.strptime(f"{parts[i]} {parts[i + 1]}", DB_FMT)
        except ValueError:
            continue
        return iso_utc(dt.replace(tzinfo=tzinfo(tz)))
    return None
