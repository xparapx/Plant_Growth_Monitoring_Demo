"""
Plant Hub -- MQTT subscriber + SQLite writer   (runs on PC or Pi, unchanged)

subscribe : plant/+/env    -> readings   (5-min bucket, ONE env node = the box)
            plant/+/soil   -> soil       (5-min bucket, one row PER PLANT)
            plant/+/pump   -> pump_log   (event: irrigation record)
            plant/+/growth -> growth     (daily, one row PER PLANT)
store     : SQLite (plant.db) -- single source of truth
time      : ts is UTC.  +9h KST applied only at display/analysis time.
"""
import json, sqlite3, signal, sys
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT   = 1883
DB     = "plant.db"

sys.stdout.reconfigure(line_buffering=True)

conn = sqlite3.connect(DB, check_same_thread=False)

# environment = the whole grow box.  ONE node.  no soil here.
conn.execute("""
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
)""")

# soil = per pot.  one watering node per plant.
conn.execute("""
CREATE TABLE IF NOT EXISTS soil(
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  ts       TEXT DEFAULT CURRENT_TIMESTAMP,
  node     TEXT,
  plant_id TEXT,   -- p1..p6
  treat    TEXT,   -- A (well-watered) | B (deficit)
  pct      REAL,
  n        INTEGER
)""")

conn.execute("""
CREATE TABLE IF NOT EXISTS pump_log(
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          TEXT DEFAULT CURRENT_TIMESTAMP,
  node        TEXT,
  plant_id    TEXT,
  treat       TEXT,
  dur_ms      INTEGER,
  soil_before REAL,
  soil_after  REAL,
  reason      TEXT    -- filled | verify_fail | manual
)""")

conn.execute("""
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
                      --   -> dashboard draws old/new overlay directly from this
  ok        INTEGER
)""")
conn.commit()

def ins(table, d, cols):
    vals = [d.get(c) for c in cols]
    t = d.get("t")
    ph = ",".join(["?"] * len(cols))
    if t:
        conn.execute(f"INSERT INTO {table}(ts,{','.join(cols)}) VALUES(?,{ph})",
                     (t, *vals))
    else:
        conn.execute(f"INSERT INTO {table}({','.join(cols)}) VALUES({ph})", vals)
    conn.commit()

def on_connect(c, u, f, rc, props):
    print(f"broker connect: {rc}")
    for t in ("plant/+/env", "plant/+/soil", "plant/+/pump", "plant/+/growth"):
        c.subscribe(t)

def on_message(c, u, msg):
    try:
        d = json.loads(msg.payload.decode())
    except Exception as e:
        print(f"parse failed: {e}")
        return

    if msg.topic.endswith("/env"):
        ins("readings", d, ["node", "temp", "hum", "press", "vpd", "lux", "co2", "n"])
        print(f"env  : {d}")

    elif msg.topic.endswith("/soil"):
        ins("soil", d, ["node", "plant_id", "treat", "pct", "n"])
        print(f"soil : {d}")

    elif msg.topic.endswith("/pump"):
        ins("pump_log", d, ["node", "plant_id", "treat", "dur_ms",
                            "soil_before", "soil_after", "reason"])
        flag = "  <<< CHECK TUBE/RESERVOIR" if d.get("reason") == "verify_fail" else ""
        print(f"pump : {d}{flag}")

    elif msg.topic.endswith("/growth"):
        # one photo -> many plants: expand list into one row per plant
        for p in d.get("plants", []):
            p["t"] = d.get("t")
            ins("growth", p,
                ["plant_id", "treat", "phase", "area_cm2", "area_px", "px_per_cm",
                 "img_file", "contour", "ok"])
        print(f"growth: {len(d.get('plants', []))} plants")

def shutdown(signum, frame):
    print("shutting down...")
    try: client.disconnect()
    except Exception: pass
    try: conn.close()
    except Exception: pass
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT,  shutdown)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, keepalive=60)
client.loop_forever()
