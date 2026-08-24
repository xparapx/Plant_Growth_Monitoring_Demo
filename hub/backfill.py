"""
backfill.py — 이미 찍혀 있는 사진을 측정해 DB 에 넣는다.

  uv run python backfill.py photos/raw/2026-08-01_1500.jpg          보기만 함
  uv run python backfill.py photos/raw/2026-08-01_1500.jpg --yes    실제로 발행

언제 쓰나
  촬영은 됐는데 측정이 실패해 growth 행이 없는 경우. 2026-08-01 이 그랬다 —
  cv2.logPolar 이 최신 OpenCV 에서 사라져 frame_align 이 예외를 던졌고,
  run_capture 가 measure() 에서 죽어 사진만 남고 DB 는 비었다.

  run_capture.py --replay 는 photos/growth.jsonl 을 다시 보내는 것이라
  이 경우에는 못 쓴다. 그때는 JSONL 에 적히기 <전에> 죽었기 때문이다
  (measure -> JSONL 기록 -> 발행 순서).

★ 쓰기 전에 확인할 것
  ROI·배율·카메라 설정이 그 사진을 찍을 때와 <지금이 같아야> 한다.
  ROI 를 다시 잡았거나 px_per_cm_ref 를 바꿨다면 지금 설정으로 옛 사진을 재는 셈이라,
  오류 없이 <그럴듯하게 틀린 숫자>가 나온다. 그게 가장 위험하다.
  그런 경우에는 넣지 말고 사진만 증거로 남겨둘 것.

시각은 파일명에서 가져온다. 지금 시각으로 넣으면 그래프의 가로축이 어긋난다.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import leaf_measure
from run_capture import CFG_PATH, DBG, JSONL, MASK, TOPIC, publish

STEM = re.compile(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})(\d{2})")


def when(path):
    """파일명 2026-08-01_1500 -> UTC. 파일명은 로컬(KST) 기준으로 붙는다."""
    m = STEM.search(os.path.basename(path))
    if not m:
        return None
    y, mo, d, h, mi = (int(x) for x in m.groups())
    local = datetime(y, mo, d, h, mi)
    return local - timedelta(hours=9)          # KST -> UTC


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--phase", choices=["dawn", "pm"],
                    help="기본: 파일명 시각으로 판단 (12시 전이면 dawn)")
    ap.add_argument("--yes", action="store_true", help="실제로 JSONL 기록 + MQTT 발행")
    a = ap.parse_args()

    if not os.path.exists(a.image):
        print(f"없는 파일: {a.image}")
        return 1

    t = when(a.image)
    if t is None:
        print(f"파일명에서 시각을 못 읽었습니다: {os.path.basename(a.image)}\n"
              f"  기대 형식: 2026-08-01_1500.jpg")
        return 1

    ph = a.phase or ("dawn" if (t + timedelta(hours=9)).hour < 12 else "pm")
    cfg = json.load(open(CFG_PATH, encoding="utf-8"))
    for d in (MASK, DBG):
        os.makedirs(d, exist_ok=True)

    print(f"\n사진   {a.image}")
    print(f"시각   {t:%Y-%m-%d %H:%M:%S} UTC  ({t + timedelta(hours=9):%H:%M} KST) · phase={ph}")
    print(f"배율   {cfg.get('qc', {}).get('px_per_cm_ref')} px/cm · "
          f"ROI {[(r['plant_id'], r['w']) for r in cfg.get('rois', [])]}")

    rows = leaf_measure.measure(a.image, ph, DBG, MASK, cfg)
    print()
    for r in rows:
        print(f"  {r['plant_id']:>4} {str(r['area_cm2']):>8} cm2  "
              f"{'ok' if r['ok'] else 'NG'}  {'contour' if r['contour'] else 'NO CONTOUR'}")

    ok = sum(r["ok"] for r in rows)
    if ok == 0:
        print("\n  ⚠ 유효한 측정이 없습니다 — photos/debug/ 를 보세요. 넣지 않습니다.")
        return 1

    payload = json.dumps({"t": f"{t:%Y-%m-%d %H:%M:%S}", "phase": ph,
                          "img": os.path.basename(a.image), "plants": rows},
                         ensure_ascii=False)

    if not a.yes:
        print(f"\n  {ok}/{len(rows)} ok — debug/mask 는 만들었습니다. DB 에는 넣지 않았습니다.")
        print(f"  넣으려면:  uv run python backfill.py {a.image} --yes\n")
        return 0

    with open(JSONL, "a", encoding="utf-8") as f:      # ★ 발행보다 먼저
        f.write(payload + "\n")
    sent, err = publish(payload)
    print(f"\n  {ok}/{len(rows)} ok  ->  "
          + (f"{TOPIC} 발행" if sent else f"발행 실패({err}) — {JSONL} 에는 저장됨"))
    print("  몇 초 뒤 DB 를 확인하세요.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
