from datetime import datetime, timezone

from plantsvc.timeutil import (
    add_minutes,
    db_ts,
    iso_utc,
    local_day,
    local_stem,
    next_occurrence,
    parse_db_ts,
    phase_now,
    seconds_between_hhmm,
)


def test_parse_variants():
    a = parse_db_ts("2026-08-01 06:00:03")
    b = parse_db_ts("2026-08-01T06:00:03Z")
    c = parse_db_ts("2026-08-01T15:00:03+09:00")
    assert a == b and a.tzinfo is not None
    assert c == a
    assert parse_db_ts("") is None and parse_db_ts("garbage") is None
    assert iso_utc(a) == "2026-08-01T06:00:03Z"
    assert db_ts(a) == "2026-08-01 06:00:03"


def test_local_helpers():
    t = datetime(2026, 8, 1, 21, 5, tzinfo=timezone.utc)           # 06:05 KST next day
    assert str(local_day(t, "Asia/Seoul")) == "2026-08-02"
    assert local_stem(t, "Asia/Seoul") == "2026-08-02_0605"
    assert phase_now("Asia/Seoul", t) == "dawn"
    assert phase_now("Asia/Seoul", datetime(2026, 8, 1, 6, 0, tzinfo=timezone.utc)) == "pm"   # 15:00 KST
    nxt = next_occurrence("05:50", "Asia/Seoul", after=t)
    assert nxt > t and nxt.astimezone().hour in range(24)
    assert add_minutes("05:50", 5) == "05:55" and add_minutes("23:58", 5) == "00:03"
    assert seconds_between_hhmm("05:55", "06:00") == 300 and seconds_between_hhmm("06:05", "06:00") < 0
