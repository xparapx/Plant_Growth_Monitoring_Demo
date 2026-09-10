import json

from plantsvc.cli import main


def test_version_seed_doctor(paths, capsys):
    assert main(["version"]) == 0
    assert main(["--data-dir", str(paths.data_dir), "seed", "--days", "2"]) == 0
    assert main(["--data-dir", str(paths.data_dir), "seed", "--days", "2"]) == 1        # refuses to overwrite
    assert paths.db.exists()
    capsys.readouterr()                                   # drop version/seed output
    rc = main(["--data-dir", str(paths.data_dir), "doctor", "--json"])
    rows = json.loads(capsys.readouterr().out)
    assert rc in (0, 1) and isinstance(rows, list) and any(r["name"] == "plant.db" for r in rows)


def test_doctor_rows_and_check_config(paths, capsys):
    from plantsvc import doctor
    from plantsvc.settings import Settings
    rows = doctor.run(Settings(data_dir=paths.data_dir, fake_hw=True), paths)
    names = {r["name"] for r in rows}
    assert {"venv", "config.json", "data dir", "camera", "led", "schedule"} <= names
    led = next(r for r in rows if r["name"] == "led")
    assert led["status"] == "SKIP"
    assert main(["--data-dir", str(paths.data_dir), "check-config"]) == 1               # no rois yet
    out = capsys.readouterr().out
    assert "px_per_cm_ref" in out


def test_render_units(paths, tmp_path):
    tdir = paths.repo_root / "deploy" / "systemd"
    if not tdir.exists():
        import pytest
        pytest.skip("deploy templates not present yet")
    out = tmp_path / "units"
    assert main(["--data-dir", str(paths.data_dir), "render-units", "--user", "plantqa", "--out", str(out)]) == 0
    files = list(out.glob("*"))
    assert files
    for f in files:
        txt = f.read_text(encoding="utf-8")
        assert "${" not in txt and "\r\n" not in txt, f.name
        if f.suffix == ".service":
            assert "User=plantqa" in txt, f.name
    timer = (out / "plantsnap.timer").read_text(encoding="utf-8")
    assert "OnCalendar=*-*-* 05:50:00" in timer and "AccuracySec=1s" in timer
