"""
plantlink -- USB serial <-> local MQTT bridge for the env node (UNO R4 WiFi, LINK_MODE=1)

Why: the school mesh Wi-Fi isolates clients on different mesh units, and WiFiS3's blocking
connect calls trip the R4 watchdog whenever the broker is unreachable. A USB cable to the Pi
removes both problems. The hub/collector/UI do not change: this process republishes the node's
lines on the same MQTT topics the Wi-Fi firmware used.

Line protocol (115200 8N1, one line per message)
  node -> Pi : "PUB <topic> <json>"   republished verbatim to the local broker
               anything else          logged (boot banner, sensor status, [LIGHT] ...)
  Pi -> node : "T <epoch>"            UTC time, sent on connect and every TIME_EVERY_S
               "L 1" / "L 0"          light command, forwarded from plant/light/set and
                                       plant/<node>/light/set (the web UI's light buttons)

Port: PLANT_SERIAL_PORT, else the first /dev/serial/by-id/usb-Arduino*UNO_R4* device, else /dev/ttyACM0.
Reconnects forever if the cable is pulled; the node keeps an 8-slot queue on its side meanwhile.
"""
import glob
import json
import os
import sys
import threading
import time

import serial  # pyserial

import paho.mqtt.client as mqtt

BROKER = os.environ.get("PLANT_MQTT_HOST", "localhost")
PORT = int(os.environ.get("PLANT_MQTT_PORT", "1883"))
BAUD = 115200
TIME_EVERY_S = 300   # R4 RTC 는 수정 발진자가 없어(LOCO) 시간당 1분 이상 흐른다 — 10/7 새벽 창이 44~90초 일찍 열리고 닫힌 것을 보고 5분으로
LIGHT_TOPICS = ("plant/light/set", "plant/+/light/set")
GROW_TICK_S = 60          # config.json 재확인·판정 주기
GROW_REFRESH_S = 600      # 창 안에서 'L 1' 재전송 주기 (노드 30분 자동소등보다 짧게)
CONFIG_PATH = os.path.join(os.environ.get("PLANT_DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")), "config.json")

sys.stdout.reconfigure(line_buffering=True)


def _hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


class Grow:
    """config.json 의 light.grow 창을 읽어 환경노드 LED 를 켜 둔다 (호스트 주도, 펌웨어 변경 없음)."""
    def __init__(self) -> None:
        self.want = False
        self.last_sent = 0.0
        self.last_state: bool | None = None

    def desired(self, now: float) -> tuple[bool, str]:
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            return False, "no config"
        g = cfg.get("light") or {}
        if not g.get("enabled"):
            return False, "disabled"
        from zoneinfo import ZoneInfo
        from datetime import datetime
        tz = ZoneInfo(cfg.get("tz") or "Asia/Seoul")
        lt = datetime.fromtimestamp(now, tz)
        if g.get("until") and lt.strftime("%Y-%m-%d") > str(g["until"]):
            return False, f"ended {g['until']}"
        cur = lt.hour * 60 + lt.minute
        on, off = _hhmm(g.get("on", "07:00")), _hhmm(g.get("off", "20:00"))
        inside = on <= cur < off if on <= off else (cur >= on or cur < off)
        if not inside:
            return False, "outside window"
        pause = int(g.get("pause_around_pm_min", 10) or 0)
        pm = (cfg.get("schedule") or {}).get("pm")
        if pause and pm:
            if abs(cur - _hhmm(pm)) <= pause:
                return False, f"pause around pm {pm}"
        return True, "window"

    def tick(self, link: "Link", now: float) -> None:
        want, why = self.desired(now)
        if want and (now - self.last_sent >= GROW_REFRESH_S or self.last_state is not True):
            link.send("L 1"); self.last_sent = now
        elif not want and self.last_state is True:
            link.send("L 0")
        if want != self.last_state:
            print(f"[GROW] {'on' if want else 'off'} ({why})")
            self.last_state = want


def find_port() -> str | None:
    p = os.environ.get("PLANT_SERIAL_PORT")
    if p and os.path.exists(p):
        return p
    for pat in ("/dev/serial/by-id/usb-Arduino*UNO_R4*", "/dev/serial/by-id/usb-Arduino*"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[0]
    return "/dev/ttyACM0" if os.path.exists("/dev/ttyACM0") else None


class Link:
    def __init__(self) -> None:
        self.ser: serial.Serial | None = None
        self.lock = threading.Lock()
        self.node_id: str | None = None

    def send(self, line: str) -> None:
        with self.lock:
            if self.ser is None:
                return
            try:
                self.ser.write((line + "\n").encode())
            except Exception as e:  # cable pulled mid-write; reader loop will reopen
                print(f"[LINK] write failed: {e}")

    def send_time(self) -> None:
        self.send(f"T {int(time.time())}")


link = Link()
grow = Grow()


def on_connect(c, u, f, rc, props):
    print(f"broker connect: {rc}")
    for t in LIGHT_TOPICS:
        c.subscribe(t)


def on_message(c, u, msg):
    if getattr(msg, "retain", False):
        # a retained "1" would re-light the strip on every bridge restart -- commands are momentary
        print(f"[LINK] ignored retained {msg.topic}")
        return
    v = msg.payload.decode(errors="replace").strip().lower()
    parts = msg.topic.split("/")
    # plant/<node>/light/set only for our node; plant/light/set is broadcast
    if len(parts) == 4 and link.node_id and parts[1] != link.node_id:
        return
    if v in ("1", "on"):
        link.send("L 1")
    elif v in ("0", "off"):
        link.send("L 0")
    else:
        print(f"[LINK] ignored light payload {v!r}")


def main() -> int:
    mq = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="plantlink")
    mq.on_connect = on_connect
    mq.on_message = on_message
    mq.connect(BROKER, PORT, 60)
    mq.loop_start()

    while True:
        port = find_port()
        if not port:
            print("[LINK] no serial device -- waiting for the env node on USB")
            time.sleep(5)
            continue
        try:
            ser = serial.Serial(port, BAUD, timeout=1)
        except Exception as e:
            print(f"[LINK] open {port} failed: {e}")
            time.sleep(5)
            continue
        print(f"[LINK] open {port}")
        with link.lock:
            link.ser = ser
        time.sleep(1.5)  # let the board settle after (re)enumeration
        link.send_time()
        last_time = time.time()
        last_grow = 0.0
        try:
            while True:
                raw = ser.readline()
                if time.time() - last_time >= TIME_EVERY_S:
                    link.send_time()
                    last_time = time.time()
                if time.time() - last_grow >= GROW_TICK_S:
                    last_grow = time.time()
                    grow.tick(link, last_grow)
                if not raw:
                    continue
                line = raw.decode(errors="replace").rstrip("\r\n")
                if line.startswith("PUB "):
                    try:
                        _, topic, payload = line.split(" ", 2)
                    except ValueError:
                        print(f"[LINK] bad PUB line: {line[:120]!r}")
                        continue
                    mq.publish(topic, payload)
                    seg = topic.split("/")
                    if len(seg) >= 2 and link.node_id != seg[1]:
                        link.node_id = seg[1]
                        print(f"[LINK] node id {link.node_id}")
                elif line.startswith("LINK: usb-serial"):
                    print(f"node: {line}")
                    link.send_time()  # the node just booted -- give it the clock now
                else:
                    print(f"node: {line}")
        except Exception as e:
            print(f"[LINK] serial error: {e} -- reopening")
        finally:
            with link.lock:
                link.ser = None
            try:
                ser.close()
            except Exception:
                pass
            time.sleep(2)


if __name__ == "__main__":
    raise SystemExit(main())
