"""
validate -- ground-truth check with paper leaves of KNOWN area.
    uv run python validate.py truth.json calib.jpg
truth.json:  {"p1": 50.0}
"""
import json, sys
from leafcv import measure

truth = json.load(open(sys.argv[1]))
rows  = measure(sys.argv[2], debug_dir="debug")

print(f'{"plant":6}{"true":>9}{"meas":>9}{"err":>9}{"err%":>8}  ok')
print("-" * 50)
errs = []
for r in rows:
    t, m = truth.get(r["plant_id"]), r["area_cm2"]
    if t is None or m is None:
        print(f'{r["plant_id"]:6}{"-":>9}{"-":>9}{"-":>9}{"-":>8}  {r["ok"]}')
        continue
    e = m - t; ep = 100.0 * e / t
    errs.append(ep)
    print(f'{r["plant_id"]:6}{t:9.1f}{m:9.1f}{e:+9.2f}{ep:+8.1f}  {r["ok"]}')

if errs:
    mae  = sum(abs(x) for x in errs) / len(errs)
    bias = sum(errs) / len(errs)
    print("-" * 50)
    print(f"mean |err| = {mae:5.2f} %     bias = {bias:+5.2f} %")
    print("PASS" if mae < 5.0 else "FAIL")
