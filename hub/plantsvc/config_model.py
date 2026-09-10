"""config.json as a typed model.

Everything an operator can set lives in ONE file (data/config.json).  The
vision code still consumes the plain-dict shape (`to_legacy_dict()`), so the
numbers and key names are exactly those setup_camera / leaf_measure /
frame_align always used.  New sections (tz, bands, analysis, led, schedule,
mqtt, preview) carry the constants that were previously duplicated in
dashboard.py, water_node.ino and the systemd units.

`migrate()` upgrades a legacy file in place: dead keys are dropped with a
warning, missing sections get defaults, malformed scalars are normalised.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .timeutil import DEFAULT_TZ, parse_hhmm

TREATS = ("stable", "fluct")
CONFIG_VERSION = 2


class Layout(BaseModel):
    cols: int = 3
    rows: int = 2
    pot_cm: float = 15.0     # ruler-measured pot diameter; used only to sanity-check the scale
    gap_cm: float = 20.0


class Capture(BaseModel):
    size: tuple[int, int] = (4608, 2592)
    lens_position: float = 1.82        # dioptres = 1/m
    exposure_us: int = 20000
    gain: float = 2.0
    colour_gains: tuple[float, float] = (1.8, 1.6)   # (red, blue)


class Roi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    plant_id: str
    treat: str = ""                   # 'stable' | 'fluct' | '' - the label source of truth
    x: int
    y: int
    w: int
    h: int

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


class QC(BaseModel):
    px_per_cm_ref: float = 0.0        # 0 => area_cm2 null and ok=0 everywhere
    edge_tol: float = 0.02
    drift_warn_px: float = 8.0
    drift_fail_px: float = 40.0
    drift_resp_min: float = 0.05


class Bands(BaseModel):
    """Treatment bands in RAW ADC counts (wet, dry) - must match water_node.ino RAW_ON/RAW_OFF -
    and the per-node calibration (RAW_DRY, RAW_WET) used to turn raw into a percentage."""
    raw: dict[str, tuple[int, int]] = Field(
        default_factory=lambda: {"stable": (1900, 1940), "fluct": (1820, 2020)})
    cal_default: tuple[int, int] = (2120, 1750)
    cal: dict[str, tuple[int, int]] = Field(default_factory=dict)

    def pct_of(self, raw: float, plant_id: str | None = None) -> float:
        dry, wet = self.cal.get(plant_id or "", self.cal_default)
        return 100.0 * (dry - raw) / float(dry - wet)

    def band_pct(self) -> dict[str, tuple[float, float]]:
        """(low %, high %) per treatment."""
        out = {}
        for t, (wet_raw, dry_raw) in self.raw.items():
            lo, hi = self.pct_of(dry_raw), self.pct_of(wet_raw)
            out[t] = (min(lo, hi), max(lo, hi))
        return out


class Analysis(BaseModel):
    tol_pp: float = 2.0            # |mu_s - mu_f| tolerance, percentage points
    sep_ratio: float = 2.0         # sigma_f / sigma_s must be >= this
    hist_bins: int = 44
    soil_days: int = 7
    pump_limit: int = 200
    dummy_fill: Literal["auto", "on", "off"] = "auto"
    env_interval_min: int = 5
    soil_interval_min: int = 5
    cam_interval_min: int = 720


class Led(BaseModel):
    """Capture light.  Hardware is not installed yet: driver 'noop' is the default and the
    routine still walks led_on -> warmup -> shoot -> led_off so the UI/API shapes are final."""
    enabled: bool = False
    driver: Literal["auto", "gpiozero", "noop"] = "noop"
    pin: int = 17                  # BCM numbering
    active_high: bool = True
    warmup_s: int = 300
    max_on_s: int = 1200           # watchdog: never leave the lamp on longer than this


class Schedule(BaseModel):
    dawn: str = "05:50"            # local wall clock (config.tz); shot lands before 06:00
    pm: str = "15:00"

    @field_validator("dawn", "pm")
    @classmethod
    def _hhmm(cls, v: str) -> str:
        h, m = parse_hhmm(v)
        return f"{h:02d}:{m:02d}"


class Mqtt(BaseModel):
    host: str = "localhost"
    port: int = 1883
    growth_topic: str = "plant/tray/growth"


class Preview(BaseModel):
    size: tuple[int, int] = (1280, 720)
    jpeg_quality: int = 80
    frame_ms: int = 80


class Config(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: int = CONFIG_VERSION
    tz: str = DEFAULT_TZ
    layout: Layout = Field(default_factory=Layout)
    capture: Capture = Field(default_factory=Capture)
    rois: list[Roi] = Field(default_factory=list)
    qc: QC = Field(default_factory=QC)
    treat_mode: str = ""           # 'random' | 'manual' | '' - provenance of the assignment
    run_started: str | None = None
    bands: Bands = Field(default_factory=Bands)
    analysis: Analysis = Field(default_factory=Analysis)
    led: Led = Field(default_factory=Led)
    schedule: Schedule = Field(default_factory=Schedule)
    mqtt: Mqtt = Field(default_factory=Mqtt)
    preview: Preview = Field(default_factory=Preview)

    @field_validator("tz")
    @classmethod
    def _tz(cls, v: str) -> str:
        from zoneinfo import ZoneInfo
        try:
            ZoneInfo(v)
        except Exception as e:
            raise ValueError(f"unknown timezone {v!r}") from e
        return v

    @field_validator("treat_mode")
    @classmethod
    def _mode(cls, v: str) -> str:
        if v not in ("random", "manual", ""):
            raise ValueError("treat_mode must be 'random', 'manual' or ''")
        return v

    # ---- helpers ----------------------------------------------------------
    def to_legacy_dict(self) -> dict[str, Any]:
        """The plain-dict shape the vision code and legacy scripts read."""
        return self.model_dump(mode="json")

    def roi_map(self) -> dict[str, str]:
        return {r.plant_id: r.treat for r in self.rois}

    @property
    def scale(self) -> float:
        """preview px per capture px (same ISP output, so a pure proportion)."""
        return self.preview.size[0] / self.capture.size[0]


DEAD_TOP_KEYS = ("marker_mm", "ref_marker")
DEAD_QC_KEYS = ("px_per_cm_tol",)


def migrate(raw: dict[str, Any] | None, *, strict: bool = False) -> tuple[dict[str, Any], list[str]]:
    """Upgrade a legacy dict to the current shape.  Never raises on dead/odd keys.

    strict=True (API writes): only structural fixes; bad scalars (tz, schedule, treat_mode)
    are left for model validation to reject instead of being silently normalised."""
    d: dict[str, Any] = dict(raw or {})
    warnings: list[str] = []

    for k in DEAD_TOP_KEYS:
        if k in d:
            d.pop(k)
            warnings.append(f"dropped legacy key '{k}' (ArUco era; frame_align replaced it)")
    qc = d.get("qc")
    if isinstance(qc, dict):
        for k in DEAD_QC_KEYS:
            if k in qc:
                qc.pop(k)
                warnings.append(f"dropped legacy key 'qc.{k}' (never read)")
    else:
        d["qc"] = {}

    if not isinstance(d.get("rois"), list):
        d["rois"] = []
    clean_rois = []
    for r in d["rois"]:
        if not isinstance(r, dict) or "plant_id" not in r:
            warnings.append(f"dropped malformed roi entry: {r!r}")
            continue
        r = {k: v for k, v in r.items() if not str(k).startswith("_")}
        if r.get("treat") is None:
            r["treat"] = ""
        clean_rois.append(r)
    d["rois"] = clean_rois

    if not strict:
        tz = d.get("tz") or DEFAULT_TZ
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(tz)
        except Exception:
            warnings.append(f"unknown tz '{tz}' -> {DEFAULT_TZ}")
            tz = DEFAULT_TZ
        d["tz"] = tz

        if d.get("treat_mode") not in ("random", "manual", "", None):
            warnings.append(f"treat_mode {d.get('treat_mode')!r} not recognised -> ''")
            d["treat_mode"] = ""

        sched = d.get("schedule")
        if isinstance(sched, dict):
            for k, default in (("dawn", "05:50"), ("pm", "15:00")):
                v = sched.get(k, default)
                try:
                    parse_hhmm(str(v))
                except Exception:
                    warnings.append(f"schedule.{k} {v!r} is not HH:MM -> {default}")
                    sched[k] = default

    v = d.get("version")
    if v != CONFIG_VERSION:
        d["version"] = CONFIG_VERSION
        if v is not None:
            warnings.append(f"config version {v} -> {CONFIG_VERSION}")
    return d, warnings
