"""
run_capture.py — 하루 2회 촬영 -> 측정 -> 발행.  systemd timer 가 부릅니다.

  uv run python run_capture.py            시각으로 phase 판단 (12시 전이면 dawn)
  uv run python run_capture.py dawn       손으로 지정
  uv run python run_capture.py --replay   발행 못 한 측정을 다시 보냄 (사진 재촬영 없이)
  sudo systemctl start plantsnap.service  ★ 실제 타이머와 같은 경로로 시험

흐름
  ① 카메라 획득 (setup_camera.py 가 떠 있으면 재시도)
  ② config.json 의 고정 설정으로 1장  ->  photos/raw/2026-08-01_0600.jpg
  ③ leaf_measure.measure()            ->  화분별 면적·윤곽  (frame_align 이 밀림 보정)
  ④ photos/growth.jsonl 에 먼저 적고   ->  ⑤ MQTT 발행

★ ④를 ⑤보다 먼저 하는 이유
  브로커가 죽어 있어도 <측정 결과는 남아야> 합니다. 발행이 실패해도 파일에는 있으므로
  나중에 다시 보낼 수 있습니다. 6주 중 하루치를 통신 문제로 잃지 않기 위한 장치입니다.
"""
import json, os, sys, time
from datetime import datetime, timezone

import leaf_measure

CFG_PATH = "config.json"
RAW, MASK, DBG = "photos/raw", "photos/mask", "photos/debug"
JSONL = "photos/growth.jsonl"

BROKER, PORT = "localhost", 1883        # ★ 브로커가 PC면 그 IP 로
TOPIC = "plant/tray/growth"

ACQUIRE_TRIES, ACQUIRE_WAIT = 3, 30     # 카메라가 안 잡히면 30초 간격으로 3번


def phase_now():
    return "dawn" if datetime.now().hour < 12 else "pm"


def shoot(path, cfg):
    """config.json 의 값 그대로 1장. 여기서 숫자를 고치지 마세요."""
    from picamera2 import Picamera2
    from libcamera import controls
    cap = cfg["capture"]

    cam = None
    for i in range(ACQUIRE_TRIES):
        try:
            cam = Picamera2(); break
        except RuntimeError as e:
            if i == ACQUIRE_TRIES - 1:
                raise RuntimeError(
                    f"카메라를 못 잡았습니다 ({e}).\n"
                    f"  setup_camera.py 가 떠 있지 않은지 확인하세요:\n"
                    f"    pgrep -af setup_camera.py ; sudo fuser -v /dev/media0") from e
            print(f"[RETRY] 카메라 사용 중 — {ACQUIRE_WAIT}초 뒤 재시도 ({i+1}/{ACQUIRE_TRIES})")
            time.sleep(ACQUIRE_WAIT)

    try:
        cam.configure(cam.create_still_configuration(main={"size": tuple(cap["size"])}))
        cam.start()                                  # ★ start() 가 먼저
        cam.set_controls({                           # 전부 수동 — 자동이면 날마다 밝기가 달라집니다
            "AfMode": controls.AfModeEnum.Manual, "LensPosition": cap["lens_position"],
            "AeEnable": False, "ExposureTime": cap["exposure_us"], "AnalogueGain": cap["gain"],
            "AwbEnable": False, "ColourGains": tuple(cap["colour_gains"]),
        })
        time.sleep(2)                                # 설정이 실제로 반영될 시간
        cam.capture_file(path)
    finally:
        try:
            cam.stop(); cam.close()
        except Exception:
            pass


def publish(payload):
    """실패해도 예외를 던지지 않습니다 — 이미 파일에는 적혀 있습니다.

    ★ qos=1 인 이유
      publish.single() 은 보내자마자 연결을 끊습니다. qos=0 이면 브로커가 처리하기 전에
      끊겨 <조용히 사라질 수> 있습니다. qos=1 은 브로커의 확인(PUBACK)을 기다린 뒤
      끊으므로, '발행 성공' 이 실제 도착을 뜻하게 됩니다.
    """
    try:
        import paho.mqtt.publish as mqtt
        mqtt.single(TOPIC, payload, qos=1, hostname=BROKER, port=PORT)
        return True, ""
    except Exception as e:
        return False, str(e)


def replay():
    """photos/growth.jsonl 중 DB 에 없는 줄만 다시 발행합니다.
    발행이 실패했던 날의 측정을 되살릴 때 씁니다 — 사진을 다시 찍지 않아도 됩니다."""
    import sqlite3
    if not os.path.exists(JSONL):
        print(f"{JSONL} 이 없습니다"); return
    try:
        with sqlite3.connect("plant.db") as c:
            last = c.execute("SELECT MAX(ts) FROM growth").fetchone()[0] or ""
    except Exception:
        last = ""
    print(f"DB 의 마지막 growth: {last or '(없음)'}")

    sent = 0
    for line in open(JSONL, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        t = json.loads(line).get("t", "")
        if last and t <= last:
            continue
        ok, err = publish(line)
        print(f"  {t}  {'발행' if ok else '실패 ' + err}")
        sent += ok
        time.sleep(0.3)
    print(f"\n{sent}건 재발행했습니다. 몇 초 뒤 DB 를 확인하세요.")


def main():
    if "--replay" in sys.argv:
        replay(); return
    ph = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("dawn", "pm") else phase_now()
    cfg = json.load(open(CFG_PATH))
    for d in (RAW, MASK, DBG):
        os.makedirs(d, exist_ok=True)

    stem = f"{datetime.now():%Y-%m-%d_%H%M}"        # 파일명은 로컬 시각 — 촬영시각 감사용
    path = f"{RAW}/{stem}.jpg"
    print(f"[{stem}] phase={ph}")

    shoot(path, cfg)
    rows = leaf_measure.measure(path, ph, DBG, MASK, cfg)
    ok = sum(r["ok"] for r in rows)

    payload = json.dumps({"t": f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                          "phase": ph, "img": os.path.basename(path), "plants": rows},
                         ensure_ascii=False)

    with open(JSONL, "a", encoding="utf-8") as f:     # ★ 발행보다 먼저
        f.write(payload + "\n")

    sent, err = publish(payload)
    print(f"[{stem}] {ph}  {ok}/{len(rows)} ok  ->  "
          + (f"{TOPIC} 발행" if sent else f"발행 실패({err}) — {JSONL} 에는 저장됨"))
    for r in rows:
        print(f"  {r['plant_id']:>4} {str(r['area_cm2']):>8} cm2  "
              f"{'ok' if r['ok'] else 'NG'}  {'contour' if r['contour'] else 'NO CONTOUR'}")

    if ok == 0:
        print("  ⚠ 유효한 측정이 하나도 없습니다 — photos/debug/ 를 확인하세요")
        sys.exit(1)                                   # systemd 가 failed 로 기록하게


if __name__ == "__main__":
    main()
