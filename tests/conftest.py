"""Shared fixtures: every test runs against a temporary PLANT_DATA_DIR with fake hardware."""

from __future__ import annotations

import pytest


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PLANT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PLANT_FAKE_HW", "1")
    monkeypatch.setenv("PLANT_MQTT", "0")
    return tmp_path


@pytest.fixture
def settings(data_dir):
    from plantsvc.settings import Settings
    return Settings(data_dir=data_dir, fake_hw=True, mqtt=False, preview_idle_close_s=1)


@pytest.fixture
def paths(settings):
    return settings.paths.ensure()


@pytest.fixture
def store(paths):
    from plantsvc.config_store import ConfigStore
    s = ConfigStore(paths.config, example=paths.example_config)
    s.load()
    return s


@pytest.fixture
def seeded(settings, paths, store):
    """A dummy plant.db (node='dummy') exactly as `plantsvc seed` makes it."""
    from argparse import Namespace

    from plantsvc.cli import cmd_seed
    assert cmd_seed(Namespace(data_dir=paths.data_dir, days=5, force=True)) == 0
    return paths


@pytest.fixture(autouse=True)
def never_publish(monkeypatch):
    """Tests must never talk to a real broker (a mosquitto may be running on the dev PC)."""
    calls: list[str] = []

    def stub(payload, *a, **k):
        calls.append(payload)
        return True, ""
    monkeypatch.setattr("plantsvc.capture.publisher.publish", stub)
    monkeypatch.setattr("plantsvc.capture.replay.publish", stub)
    monkeypatch.setattr("plantsvc.capture.runner._publish", stub)
    return calls


@pytest.fixture
def context(settings, never_publish):
    from plantsvc.context import build_context
    ctx = build_context(settings, mqtt=False, log=lambda *_: None)
    ctx.runner._publish = lambda payload, *a, **k: (never_publish.append(payload) or (True, ""))
    yield ctx
    ctx.close()


@pytest.fixture
def client(settings, never_publish):
    from fastapi.testclient import TestClient

    from plantsvc.app import create_app
    app = create_app(settings, mqtt=False)
    app.state.ctx.runner._publish = lambda payload, *a, **k: (never_publish.append(payload) or (True, ""))
    with TestClient(app) as c:
        yield c
