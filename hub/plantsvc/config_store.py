"""Atomic, mtime-aware access to data/config.json.

`save_atomic` is the one from center_roi.py: open(path,'w') truncates the file
the moment it opens, so a crash mid-write leaves config.json - the single
source of the treatment assignment - empty.  Write a temp file, fsync,
os.replace.

The store re-reads the file when its mtime changes, because legacy CLIs
(reset_run.py, center_roi.py --yes) still write it directly.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .config_model import Config, migrate


def save_atomic(path: str | os.PathLike, data: Any) -> None:
    path = os.fspath(path)
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


class ConfigError(RuntimeError):
    pass


class ConfigStore:
    def __init__(self, path: str | os.PathLike, *, example: str | os.PathLike | None = None):
        self.path = Path(path)
        self.example = Path(example) if example else None
        self._lock = threading.RLock()
        self._cfg: Config | None = None
        self._mtime_ns: int | None = None
        self.warnings: list[str] = []
        self._callbacks: list[Callable[[Config], None]] = []

    # ---- reading ----------------------------------------------------------
    def _stat_ns(self) -> int | None:
        try:
            return self.path.stat().st_mtime_ns
        except FileNotFoundError:
            return None

    def load(self) -> Config:
        with self._lock:
            if not self.path.exists():
                seed: dict[str, Any] = {}
                if self.example and self.example.exists():
                    try:
                        seed = json.loads(self.example.read_text(encoding="utf-8"))
                    except json.JSONDecodeError as e:
                        raise ConfigError(f"example config is not valid JSON: {e}") from e
                data, warns = migrate(seed)
                cfg = self._validate(data)
                save_atomic(self.path, cfg.model_dump(mode="json"))
                self.warnings = warns + [f"created {self.path} from defaults"]
            else:
                try:
                    raw = json.loads(self.path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as e:
                    raise ConfigError(
                        f"{self.path} is not valid JSON: {e}  (JSON has no // comments)") from e
                data, warns = migrate(raw)
                cfg = self._validate(data)
                self.warnings = warns
                if warns:
                    # persist the migrated shape so the warning shows once, not forever
                    save_atomic(self.path, cfg.model_dump(mode="json"))
            self._cfg = cfg
            self._mtime_ns = self._stat_ns()
            return cfg

    def _validate(self, data: dict[str, Any]) -> Config:
        try:
            return Config.model_validate(data)
        except ValidationError as e:
            raise ConfigError(f"{self.path}: {e.errors()[0]['loc']} - {e.errors()[0]['msg']}") from e

    def get(self) -> Config:
        with self._lock:
            if self._cfg is None or self._stat_ns() != self._mtime_ns:
                self.load()
            assert self._cfg is not None
            return self._cfg

    def legacy(self) -> dict[str, Any]:
        return self.get().to_legacy_dict()

    @property
    def mtime_ns(self) -> int | None:
        return self._mtime_ns

    # ---- writing ----------------------------------------------------------
    def save(self, cfg: Config) -> Config:
        with self._lock:
            save_atomic(self.path, cfg.model_dump(mode="json"))
            self._cfg = cfg
            self._mtime_ns = self._stat_ns()
        for cb in list(self._callbacks):
            try:
                cb(cfg)
            except Exception:  # a broken listener must not block a save
                pass
        return cfg

    def update(self, fn: Callable[[Config], None]) -> Config:
        with self._lock:
            cfg = self.get().model_copy(deep=True)
            fn(cfg)
            return self.save(cfg)

    def replace(self, data: dict[str, Any]) -> Config:
        """Full replacement from an untrusted dict (API PUT).  Raises ConfigError."""
        migrated, _ = migrate(data, strict=True)
        cfg = self._validate(migrated)
        return self.save(cfg)

    def on_change(self, cb: Callable[[Config], None]) -> None:
        self._callbacks.append(cb)
