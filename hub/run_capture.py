"""
run_capture.py — compatibility shim.  The capture routine now lives in plantsvc:

  uv run python hub/run_capture.py            ==  plantsvc capture --phase auto
  uv run python hub/run_capture.py dawn|pm    ==  plantsvc capture --phase dawn|pm
  uv run python hub/run_capture.py --replay   ==  plantsvc replay
  sudo systemctl start plantsnap.service      ★ the real timer path

Flow (unchanged in spirit, with the LED hook added):
  ① camera lock  ② LED on → warm-up (when installed)  ③ shoot with config.json controls
  ④ leaf_measure  ⑤ growth.jsonl FIRST  ⑥ MQTT publish qos=1
"""
import sys

from plantsvc.capture.publisher import publish as _publish
from plantsvc.settings import get_paths

_P = get_paths()
CFG_PATH = str(_P.config)
RAW, MASK, DBG = str(_P.raw), str(_P.mask), str(_P.debug)
JSONL = str(_P.jsonl)
BROKER, PORT = "localhost", 1883
TOPIC = "plant/tray/growth"


def publish(payload):
    return _publish(payload, TOPIC, BROKER, PORT)


def main(argv=None):
    from plantsvc.cli import main as cli_main
    argv = sys.argv[1:] if argv is None else argv
    if "--replay" in argv:
        return cli_main(["replay"])
    phase = next((a for a in argv if a in ("dawn", "pm")), "auto")
    return cli_main(["capture", "--phase", phase])


if __name__ == "__main__":
    raise SystemExit(main())
