import json

from plantsvc.capture.runner import CaptureRunner, JobBusy
from plantsvc.vision import roi_tools


def _setup(ctx):
    from plantsvc.config_model import Roi
    cfg = ctx.store.get()

    def _u(c):
        c.rois = [Roi(**r) for r in roi_tools.grid_rois(*cfg.capture.size, 3, 2)]
        for i, r in enumerate(c.rois):
            r.treat = "stable" if i < 3 else "fluct"
        c.qc.px_per_cm_ref = 30.0
    ctx.store.update(_u)


def test_job_runs_led_hook_and_never_publishes_fake_frames(context):
    ctx = context
    _setup(ctx)
    sent = []
    ctx.runner._publish = lambda payload, *a, **k: (sent.append(payload) or (True, ""))
    job = ctx.runner.run("dawn", trigger="test", warmup_s=0)
    assert job.state == "done", job.error
    assert job.ok_rows == 6 and job.fake and job.img_file.startswith("fake_")
    names = [s["name"] for s in job.steps]
    assert names.index("led_on") < names.index("capture") < names.index("led_off") < names.index("measure") < names.index("jsonl") < names.index("publish")
    assert job.led and job.led["installed"] is False and job.warmup_s == 0
    assert job.published is False and not sent                       # fake frame -> not published
    lines = ctx.paths.jsonl.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["img"].startswith("fake_")
    assert ctx.events.jobs(1)[0]["state"] == "done"
    assert (ctx.paths.raw / job.img_file).exists()
    # the camera lock is released after the job
    assert ctx.camera.flock.held is False or ctx.camera.state == "open"


def test_debounce_force_and_if_missing(context):
    ctx = context
    _setup(ctx)
    ctx.runner._publish = lambda *a, **k: (True, "")
    first = ctx.runner.run("dawn", warmup_s=0, allow_fake_publish=True)
    assert first.state == "done" and first.published
    # fake frames are excluded from dedupe, so simulate a real entry by rewriting the img name
    p = ctx.paths.jsonl
    p.write_text(p.read_text(encoding="utf-8").replace("fake_", ""), encoding="utf-8")
    again = ctx.runner.run("dawn", warmup_s=0)
    assert again.state == "skipped" and "debounced" in again.error
    forced = ctx.runner.run("dawn", warmup_s=0, force=True)
    assert forced.state == "done"
    p.write_text(p.read_text(encoding="utf-8").replace("fake_", ""), encoding="utf-8")
    catchup = ctx.runner.run("dawn", warmup_s=0, if_missing=True)
    assert catchup.state == "skipped" and ("already captured" in catchup.error or "outside window" in catchup.error)


def test_measure_failure_marks_failed_and_led_off(context, monkeypatch):
    ctx = context
    _setup(ctx)
    from plantsvc.capture import runner as runner_mod

    def boom(*a, **k):
        raise RuntimeError("cv2 exploded")
    monkeypatch.setattr(runner_mod.leaf_measure, "measure", boom)
    job = ctx.runner.run("pm", warmup_s=0)
    assert job.state == "failed" and "cv2 exploded" in job.error
    assert "led_off" in [s["name"] for s in job.steps]
    assert ctx.led.is_on is False


def test_single_flight(context):
    ctx = context
    _setup(ctx)
    ctx.runner._lock.acquire()
    try:
        try:
            ctx.runner.run("dawn", warmup_s=0)
            raise AssertionError("expected JobBusy")
        except JobBusy:
            pass
    finally:
        ctx.runner._lock.release()
    assert isinstance(ctx.runner, CaptureRunner)
