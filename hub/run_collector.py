"""
Plant Hub -- MQTT subscriber + SQLite writer   (runs on PC or Pi, unchanged)

subscribe : plant/+/env    -> readings   (5-min bucket, ONE env node = the box)
            plant/+/soil   -> soil       (5-min bucket, one row PER PLANT)
            plant/+/pump   -> pump_log   (event: irrigation record)
            plant/+/growth -> growth     (daily, one row PER PLANT)
store     : SQLite (data/plant.db) -- single source of truth; THIS process is the only writer.
time      : ts is UTC.  Local time is applied only at display/analysis time.

Paths come from PLANT_DATA_DIR (default <repo>/data); the schema lives in
plantsvc.schema so tests and the API share one definition.
"""
import json
import os
import signal
import sqlite3
import sys

import paho.mqtt.client as mqtt

from plantsvc.schema import INSERT_COLS, configure_writer, ensure_schema
from plantsvc.settings import get_paths

BROKER = os.environ.get("PLANT_MQTT_HOST", "localhost")
PORT = int(os.environ.get("PLANT_MQTT_PORT", "1883"))
PATHS = get_paths().ensure()
DB = PATHS.db

sys.stdout.reconfigure(line_buffering=True)

conn = sqlite3.connect(DB, check_same_thread=False)
configure_writer(conn)
ensure_schema(conn)
print(f"db: {DB}")

_warned = set()


def ins(table, d, cols):
    # Keys the node sends that we have nowhere to put.  Say it once per key.
    extra = set(d) - set(cols) - {"t"}
    for k in sorted(extra):
        if (table, k) not in _warned:
            _warned.add((table, k))
            print(f"[DROP] {table}: '{k}' has no column -- value discarded. "
                  f"add it to plantsvc.schema DDL and WANT.")

    vals = [d.get(c) for c in cols]
    t = d.get("t")
    ph = ",".join(["?"] * len(cols))
    if t:
        conn.execute(f"INSERT INTO {table}(ts,{','.join(cols)}) VALUES(?,{ph})", (t, *vals))
    else:
        conn.execute(f"INSERT INTO {table}({','.join(cols)}) VALUES({ph})", vals)
    conn.commit()


def on_connect(c, u, f, rc, props):
    print(f"broker connect: {rc}")
    for t in ("plant/+/env", "plant/+/soil", "plant/+/pump", "plant/+/growth"):
        c.subscribe(t)


def on_message(c, u, msg):
    # paho swallows exceptions raised inside this callback: the collector keeps
    # running and looks healthy while nothing is written.  Catch and print.
    try:
        _handle(msg)
    except Exception as e:
        print(f"[ERROR] {msg.topic}: {type(e).__name__}: {e}")
        print(f"        payload: {msg.payload[:300]!r}")


def _handle(msg):
    try:
        d = json.loads(msg.payload.decode())
    except Exception as e:
        print(f"parse failed: {e}")
        return

    if msg.topic.endswith("/env"):
        ins("readings", d, INSERT_COLS["readings"])
        print(f"env  : {d}")

    elif msg.topic.endswith("/soil"):
        ins("soil", d, INSERT_COLS["soil"])
        print(f"soil : {d}")

    elif msg.topic.endswith("/pump"):
        ins("pump_log", d, INSERT_COLS["pump_log"])
        # the node sends 'verify fail' (space); older docs said 'verify_fail'
        flag = ("  <<< CHECK TUBE/RESERVOIR"
                if str(d.get("reason", "")).replace("_", " ") in ("verify fail", "no rise")
                else "")
        print(f"pump : {d}{flag}")

    elif msg.topic.endswith("/growth"):
        # one photo -> many plants: expand list into one row per plant
        for p in d.get("plants", []):
            p["t"] = d.get("t")
            ins("growth", p, INSERT_COLS["growth"])
        print(f"growth: {len(d.get('plants', []))} plants")


def shutdown(signum, frame):
    print("shutting down...")
    try:
        client.disconnect()
    except Exception:
        pass
    try:
        conn.close()
    except Exception:
        pass
    sys.exit(0)


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, keepalive=60)
client.loop_forever()
