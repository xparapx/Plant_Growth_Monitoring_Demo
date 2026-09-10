"""Paths and process settings.

Every file the hub touches is resolved from ONE anchor - the data directory -
never from the current working directory.  Legacy scripts used bare relative
names ("plant.db", "config.json", "photos/raw"), which meant a service started
from the wrong directory silently created a second, empty database.

    PLANT_DATA_DIR   runtime data (default: <repo>/data)
    PLANT_WEB_DIST   built React app (default: <repo>/web/dist)
    PLANT_PORT / PLANT_HOST
    PLANT_CAMERA     auto | picamera2 | fake
    PLANT_LED        auto | gpiozero | noop     (config.json led.driver is the base; env overrides)
    PLANT_FAKE_HW=1  shorthand for camera=fake + led=noop (CI, PC, other-user dry runs)
    PLANT_MQTT=0     do not connect the live-update bridge
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Paths:
    repo_root: Path
    data_dir: Path
    web_dist: Path

    # ---- derived -------------------------------------------------------
    @property
    def db(self) -> Path:
        return self.data_dir / "plant.db"

    @property
    def events_db(self) -> Path:
        return self.data_dir / "events.db"

    @property
    def config(self) -> Path:
        return self.data_dir / "config.json"

    @property
    def calib(self) -> Path:
        return self.data_dir / "calib.jpg"

    @property
    def truth(self) -> Path:
        return self.data_dir / "truth.json"

    @property
    def photos(self) -> Path:
        return self.data_dir / "photos"

    @property
    def raw(self) -> Path:
        return self.photos / "raw"

    @property
    def mask(self) -> Path:
        return self.photos / "mask"

    @property
    def debug(self) -> Path:
        return self.photos / "debug"

    @property
    def jsonl(self) -> Path:
        return self.photos / "growth.jsonl"

    @property
    def camera_lock(self) -> Path:
        return self.data_dir / "camera.lock"

    @property
    def example_config(self) -> Path:
        return self.repo_root / "hub" / "config.example.json"

    def ensure(self) -> Paths:
        for d in (self.data_dir, self.raw, self.mask, self.debug):
            d.mkdir(parents=True, exist_ok=True)
        return self

    @classmethod
    def from_env(cls, data_dir: str | os.PathLike | None = None,
                 web_dist: str | os.PathLike | None = None) -> Paths:
        dd = Path(data_dir or os.environ.get("PLANT_DATA_DIR") or REPO_ROOT / "data")
        wd = Path(web_dist or os.environ.get("PLANT_WEB_DIST") or REPO_ROOT / "web" / "dist")
        return cls(repo_root=REPO_ROOT, data_dir=dd.expanduser().resolve(),
                   web_dist=wd.expanduser().resolve())


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PLANT_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8080
    data_dir: Path | None = None
    web_dist: Path | None = None
    camera: Literal["auto", "picamera2", "fake"] = "auto"
    led: Literal["auto", "gpiozero", "noop"] | None = None
    fake_hw: bool = False
    mqtt: bool = True
    preview_idle_close_s: int = 30
    max_stream_clients: int = 3
    quiet_window_s: int = 60          # refuse to open the preview this close to a scheduled shot

    @property
    def paths(self) -> Paths:
        return Paths.from_env(self.data_dir, self.web_dist)

    @property
    def camera_mode(self) -> str:
        return "fake" if self.fake_hw else self.camera

    @property
    def led_mode(self) -> str | None:
        return "noop" if self.fake_hw else self.led


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def get_paths() -> Paths:
    """Paths for the current process (env-driven).  Cheap; safe to call repeatedly."""
    return Paths.from_env()
