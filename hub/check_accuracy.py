"""
check_accuracy.py -- ground-truth check with paper leaves of KNOWN area.
    uv run python hub/check_accuracy.py data/truth.json data/calib.jpg
truth.json:  {"p1": 50.0}     PASS if mean |err| < 5 %
"""
import json
import sys

from plantsvc.config_store import ConfigStore
from plantsvc.settings import get_paths
from plantsvc.vision.leaf_measure import measure

P = get_paths()
truth_path = sys.argv[1] if len(sys.argv) > 1 else str(P.truth)
img_path = sys.argv[2] if len(sys.argv) > 2 else str(P.calib)
truth = json.load(open(truth_path, encoding="utf-8"))
cfg = ConfigStore(P.config, example=P.example_config).get().to_legacy_dict()
rows = measure(img_path, "check", debug_dir=P.debug, C=cfg, ref_path=P.calib)

print(f'{"plant":6}{"true":>9}{"meas":>9}{"err":>9}{"err%":>8}  ok')
print("-" * 50)
errs = []
for r in rows:
    t, m = truth.get(r["plant_id"]), r["area_cm2"]
    if t is None or m is None:
        print(f'{r["plant_id"]:6}{"-":>9}{"-":>9}{"-":>9}{"-":>8}  {r["ok"]}')
        continue
    e = m - t
    ep = 100.0 * e / t
    errs.append(ep)
    print(f'{r["plant_id"]:6}{t:9.1f}{m:9.1f}{e:+9.2f}{ep:+8.1f}  {r["ok"]}')

if errs:
    mae = sum(abs(x) for x in errs) / len(errs)
    bias = sum(errs) / len(errs)
    print("-" * 50)
    print(f"mean |err| = {mae:5.2f} %     bias = {bias:+5.2f} %")
    print("PASS" if mae < 5.0 else "FAIL")
