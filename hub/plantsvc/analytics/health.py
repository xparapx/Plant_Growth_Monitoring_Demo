"""Node freshness chips, sensor-missing detection, stuck sensors, alerts.

Only REAL nodes get a status colour - a dummy node shown green would be a lie.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..config_model import Config
from ..db import Frames
from ..timeutil import iso_utc
from .roster import Roster

BME_KEYS = ("temp", "hum", "press", "vpd")
ENV_KEYS = ("vpd", "temp", "hum", "co2", "lux")
ENV_META = {
    "vpd": {"label": "VPD", "unit": "kPa", "digits": 2},
    "temp": {"label": "Temp", "unit": "°C", "digits": 1},
    "hum": {"label": "RH", "unit": "%", "digits": 0},
    "co2": {"label": "CO₂", "unit": "ppm", "digits": 0},
    "lux": {"label": "Light", "unit": "lx", "digits": 0},
}


def missing(env: pd.DataFrame, key: str) -> bool:
    """이 값이 실측인지 아닌지. 결측이면 True.  temp·hum 이 동시에 0 이면 센서 미연결."""
    if env.empty or key not in env.columns:
        return True
    v = env[key].tail(12)
    if v.isna().all():
        return True
    if key in BME_KEYS and "temp" in env.columns and "hum" in env.columns:
        t, h = env["temp"].tail(12), env["hum"].tail(12)
        if (t.abs() < 0.05).all() and (h.abs() < 0.05).all():
            return True
    return False


def _minutes_ago(now: pd.Timestamp | None, ts: pd.Timestamp | None) -> int | None:
    if now is None or ts is None or pd.isna(ts):
        return None
    return int((now - ts).total_seconds() // 60)


def env_summary(fr: Frames, spark_points: int = 288) -> dict[str, Any]:
    env = fr.env
    out: dict[str, Any] = {}
    if env.empty:
        for k in ENV_KEYS:
            out[k] = {**ENV_META[k], "value": None, "delta_1d": None, "missing": True, "spark": []}
        return out
    cur = env.iloc[-1]
    day = env.iloc[max(0, len(env) - 288)]
    for k in ENV_KEYS:
        miss = missing(env, k)
        tail = env[k].tail(spark_points) if k in env.columns else pd.Series(dtype=float)
        spark = [None if pd.isna(x) else round(float(x), 3) for x in tail]
        val = None if miss or k not in env.columns or pd.isna(cur[k]) else float(cur[k])
        delta = None
        if not miss and k != "lux" and k in env.columns and pd.notna(day[k]) and val is not None:
            delta = float(cur[k] - day[k])
        out[k] = {**ENV_META[k], "value": val, "delta_1d": delta, "missing": miss,
                  "spark": [] if miss else spark}
    return out


def nodes_and_alerts(fr: Frames, roster: Roster, cfg: Config) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    env_every = cfg.analysis.env_interval_min
    soil_every = cfg.analysis.soil_interval_min
    cam_every = cfg.analysis.cam_interval_min
    now = fr.now
    nodes: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []

    def chip(name: str, kind: str, mins: int | None, *, every: int, real: bool,
             stuck: bool = False, pot: str | None = None, last_ts=None) -> None:
        if not real:
            state = "off"
        else:
            bad = stuck or (mins is None) or mins > every * 12
            state = "bad" if bad else ("amber" if mins > every * 4 else "ok")
        nodes.append({"name": name, "kind": kind, "pot": pot, "real": real, "state": state,
                      "minutes_ago": mins, "every_min": every, "stuck": stuck,
                      "last_ts": iso_utc(last_ts.to_pydatetime()) if last_ts is not None and pd.notna(last_ts) else None})

    env_last = fr.env.ts.max() if len(fr.env) else None
    chip("ENV", "env", _minutes_ago(now, env_last), every=env_every, real=fr.real_env,
         last_ts=env_last)

    for p in roster.pots:
        real = p in fr.real_pots
        s = fr.soil[fr.soil.plant_id == p] if len(fr.soil) else fr.soil
        tail = s.pct.tail(12) if len(s) else pd.Series(dtype=float)
        stuck = bool(real and len(tail) >= 12 and tail.nunique() == 1)
        last = s.ts.max() if len(s) else None
        chip(p.upper(), "pot", _minutes_ago(now, last), every=soil_every, real=real, stuck=stuck,
             pot=p, last_ts=last)
        if stuck:
            alerts.append({"level": "error", "code": "stuck_sensor", "pots": [p],
                           "text": f"{p.upper()} — value unchanged, node still transmitting. "
                                   f"Irrigation is running on a dead reading. Check I2C lead."})

    grow_last = fr.grow.ts.max() if len(fr.grow) else None
    cam_real = "growth" not in fr.fake and len(fr.grow) > 0
    chip("CAM", "cam", _minutes_ago(now, grow_last) if cam_real else None, every=cam_every,
         real=cam_real, last_ts=grow_last)

    if len(fr.pump) and "reason" in fr.pump.columns:
        reason = fr.pump.reason.astype(str).str.replace("_", " ", regex=False).str.strip()
        vf = fr.pump[reason == "verify fail"].plant_id.dropna().unique()
        vf = [str(v) for v in vf if v in fr.real_pots]
        if vf:
            alerts.append({"level": "error", "code": "verify_fail", "pots": vf,
                           "text": f"{', '.join(v.upper() for v in vf)} — pump ran, no moisture rise. "
                                   f"Node disarmed. Check tube and tank."})

    gone = [ENV_META[k]["label"] for k in ENV_KEYS if fr.real_env and missing(fr.env, k)]
    if gone:
        alerts.append({"level": "warn", "code": "sensor_missing", "keys": gone,
                       "text": f"{', '.join(gone)} 가 실측이 아닙니다 — BME688 미연결이거나 읽기 실패입니다. "
                               f"0 이 아니라 결측으로 기록되도록 노드 펌웨어를 고치세요."})
    if roster.unknown:
        alerts.append({"level": "error", "code": "unknown_treat", "labels": roster.unknown,
                       "sql": roster.suggested_sql(),
                       "text": f"Unrecognised treatment label(s): {roster.unknown}. Expected 'stable' or "
                               f"'fluct'. Probably left over from an MQTT test — delete them."})
    if roster.conflicts:
        alerts.append({"level": "error", "code": "treat_conflict", "pots": sorted(roster.conflicts),
                       "detail": roster.conflicts,
                       "text": "처리군 불일치 — 이 화분들은 그리지 않습니다. 펌프 호스가 실제로 꽂힌 화분을 기준으로 "
                               "water_node.ino 의 TREAT_FLUCT·PLANT_ID 와 config.json 의 rois[].treat 를 맞추세요. "
                               "과거 행을 지우기 전에 plant.db 를 백업하세요."})
    return nodes, alerts
