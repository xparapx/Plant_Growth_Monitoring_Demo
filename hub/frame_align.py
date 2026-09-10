"""frame_align.py — compatibility shim.  The implementation moved to
plantsvc.vision.frame_align (calib.jpg and config.json come from PLANT_DATA_DIR).

  uv run python hub/frame_align.py photos/raw/xxx.jpg [calib.jpg]
"""
from plantsvc.settings import get_paths
from plantsvc.vision.frame_align import (  # noqa: F401
    DEF_RESP_MIN,
    DEF_SHIFT_FAIL,
    DEF_SHIFT_WARN,
    _cli,
    align,
    shift_rois,
)

_p = get_paths()
CFG_PATH = str(_p.config)
REF_PATH = str(_p.calib)

if __name__ == "__main__":
    raise SystemExit(_cli())
