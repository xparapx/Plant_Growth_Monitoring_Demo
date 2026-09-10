"""Re-publish growth.jsonl lines that never reached plant.db (broker was down)."""

from __future__ import annotations

import json
import time
from typing import Any

from ..config_model import Config
from ..db import ro_connect
from ..settings import Paths
from .publisher import publish


def last_growth_ts(paths: Paths) -> str:
    conn = ro_connect(paths.db)
    if conn is None:
        return ""
    try:
        return conn.execute("SELECT MAX(ts) FROM growth").fetchone()[0] or ""
    except Exception:
        return ""
    finally:
        conn.close()


def jsonl_tail(paths: Paths, n: int = 20) -> list[dict[str, Any]]:
    if not paths.jsonl.exists():
        return []
    lines = [ln for ln in paths.jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
    out = []
    for ln in lines[-n:]:
        try:
            d = json.loads(ln)
            d["plants"] = [{k: v for k, v in p.items() if k != "contour"} for p in d.get("plants", [])]
            out.append(d)
        except ValueError:
            continue
    return out


def replay(paths: Paths, cfg: Config, *, log=print, allow_fake: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {"last_db_ts": last_growth_ts(paths), "sent": 0, "skipped": 0, "errors": []}
    if not paths.jsonl.exists():
        out["errors"].append(f"{paths.jsonl} 이 없습니다")
        return out
    last = out["last_db_ts"]
    for line in paths.jsonl.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            out["skipped"] += 1
            continue
        t = d.get("t", "")
        if last and t <= last:
            out["skipped"] += 1
            continue
        if str(d.get("img", "")).startswith("fake_") and not allow_fake:
            out["skipped"] += 1
            continue
        ok, err = publish(line, cfg.mqtt.growth_topic, cfg.mqtt.host, cfg.mqtt.port)
        if log:
            log(f"  {t}  {'발행' if ok else '실패 ' + err}")
        if ok:
            out["sent"] += 1
        else:
            out["errors"].append(f"{t}: {err}")
        time.sleep(0.3)
    return out
