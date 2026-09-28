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
import os
import sys
import threading
import time

import serial  # pyserial

import paho.mqtt.client as mqtt

BROKER = os.environ.get("PLANT_MQTT_HOST", "localhost")
PORT = int(os.environ.get("PLANT_MQTT_PORT", "1883"))
BAUD = 115200
TIME_EVERY_S = 3600
LIGHT_TOPICS = ("plant/light/set", "plant/+/light/set")

sys.stdout.reconfigure(line_buffering=True)


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


def on_connect(c, u, f, rc, props):
    print(f"broker connect: {rc}")
    for t in LIGHT_TOPICS:
        c.subscribe(t)


def on_message(c, u, msg):
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
        try:
            while True:
                raw = ser.readline()
                if time.time() - last_time >= TIME_EVERY_S:
                    link.send_time()
                    last_time = time.time()
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
