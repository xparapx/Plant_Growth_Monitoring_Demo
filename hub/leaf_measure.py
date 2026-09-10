"""leaf_measure.py — compatibility shim.  The implementation moved to
plantsvc.vision.leaf_measure (paths are resolved from PLANT_DATA_DIR, not CWD).

  uv run python hub/leaf_measure.py [photos/raw/xxx.jpg] [phase]
"""
from plantsvc.settings import get_paths
from plantsvc.vision.leaf_measure import _cli, leaf_mask, measure, outline  # noqa: F401

_p = get_paths()
CFG_PATH = str(_p.config)
REF_PATH = str(_p.calib)

if __name__ == "__main__":
    raise SystemExit(_cli())
