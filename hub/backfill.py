"""
backfill.py — 이미 찍혀 있는 사진을 측정해 DB 에 넣는다.

  uv run python hub/backfill.py data/photos/raw/2026-08-01_1500.jpg          보기만 함
  uv run python hub/backfill.py data/photos/raw/2026-08-01_1500.jpg --yes    실제로 발행

촬영은 됐는데 측정이 실패해 growth 행이 없는 경우에 씁니다 (run_capture --replay 는 JSONL 이
있을 때만 쓸 수 있습니다).  ★ ROI·배율·카메라 설정이 그 사진을 찍을 때와 지금이 같아야 합니다.
시각은 파일명(로컬 시각, config.tz)에서 가져옵니다.
"""
import argparse
import json
import os
import re
from datetime import datetime, timezone

from plantsvc.capture.publisher import publish
from plantsvc.config_store import ConfigStore
from plantsvc.settings import get_paths
from plantsvc.timeutil import tzinfo
from plantsvc.vision import leaf_measure

STEM = re.compile(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})(\d{2})")
P = get_paths()


def when(path, tz):
    """파일명 2026-08-01_1500 -> UTC. 파일명은 로컬(config.tz) 기준으로 붙는다."""
    m = STEM.search(os.path.basename(path))
    if not m:
        return None
    y, mo, d, h, mi = (int(x) for x in m.groups())
    return datetime(y, mo, d, h, mi, tzinfo=tzinfo(tz)).astimezone(timezone.utc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--phase", choices=["dawn", "pm"], help="기본: 파일명 시각으로 판단 (12시 전이면 dawn)")
    ap.add_argument("--yes", action="store_true", help="실제로 JSONL 기록 + MQTT 발행")
    a = ap.parse_args()

    if not os.path.exists(a.image):
        print(f"없는 파일: {a.image}")
        return 1
    cfg = ConfigStore(P.config, example=P.example_config).get()
    t = when(a.image, cfg.tz)
    if t is None:
        print(f"파일명에서 시각을 못 읽었습니다: {os.path.basename(a.image)}\n  기대 형식: 2026-08-01_1500.jpg")
        return 1
    local = t.astimezone(tzinfo(cfg.tz))
    ph = a.phase or ("dawn" if local.hour < 12 else "pm")
    C = cfg.to_legacy_dict()
    P.ensure()

    print(f"\n사진   {a.image}")
    print(f"시각   {t:%Y-%m-%d %H:%M:%S} UTC  ({local:%H:%M} {cfg.tz}) · phase={ph}")
    print(f"배율   {cfg.qc.px_per_cm_ref} px/cm · ROI {[(r.plant_id, r.w) for r in cfg.rois]}")

    rows = leaf_measure.measure(a.image, ph, P.debug, P.mask, C, ref_path=P.calib)
    print()
    for r in rows:
        print(f"  {r['plant_id']:>4} {str(r['area_cm2']):>8} cm2  "
              f"{'ok' if r['ok'] else 'NG'}  {'contour' if r['contour'] else 'NO CONTOUR'}")

    ok = sum(r["ok"] for r in rows)
    if ok == 0:
        print("\n  ⚠ 유효한 측정이 없습니다 — photos/debug/ 를 보세요. 넣지 않습니다.")
        return 1

    payload = json.dumps({"t": f"{t:%Y-%m-%d %H:%M:%S}", "phase": ph,
                          "img": os.path.basename(a.image), "plants": rows}, ensure_ascii=False)
    if not a.yes:
        print(f"\n  {ok}/{len(rows)} ok — debug/mask 는 만들었습니다. DB 에는 넣지 않았습니다.")
        print(f"  넣으려면:  uv run python hub/backfill.py {a.image} --yes\n")
        return 0

    with open(P.jsonl, "a", encoding="utf-8") as f:      # ★ 발행보다 먼저
        f.write(payload + "\n")
    sent, err = publish(payload, cfg.mqtt.growth_topic, cfg.mqtt.host, cfg.mqtt.port)
    print(f"\n  {ok}/{len(rows)} ok  ->  "
          + (f"{cfg.mqtt.growth_topic} 발행" if sent else f"발행 실패({err}) — {P.jsonl} 에는 저장됨"))
    print("  몇 초 뒤 DB 를 확인하세요.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
