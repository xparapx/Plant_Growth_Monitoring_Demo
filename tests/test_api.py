def test_read_endpoints_on_empty_data_dir_are_dummy(client):
    s = client.get("/api/summary").json()
    assert s["dummy"] == ["env", "growth", "pump", "soil"]
    assert s["validity"]["enough_groups"] and len(s["pots"]) == 6 and s["env"]["vpd"]["value"] is not None
    assert s["led"]["installed"] is False
    h = client.get("/api/health").json()
    assert {n["name"] for n in h["nodes"]} >= {"ENV", "P1", "CAM"}
    assert all(n["state"] == "off" for n in h["nodes"])                 # dummy nodes never look healthy
    e = client.get("/api/env?bucket=1h").json()
    assert e["bucket"] == 3600 and len(e["series"]["ts"]) > 24
    so = client.get("/api/soil?bucket=15m&pots=p1,p2").json()
    assert [p["plant_id"] for p in so["pots"]] == ["p1", "p2"]
    a = client.get("/api/analytics/all").json()
    for k in ("validity", "histogram", "rgr", "droop", "silhouettes", "water", "pump_recent"):
        assert k in a
    csv = client.get("/api/export/soil.csv")
    assert csv.headers.get("X-Plant-Dummy") == "1" and csv.text.startswith("ts,")


def test_seeded_db_is_real_but_flagged_by_node(client, seeded):
    s = client.get("/api/summary").json()
    assert s["dummy"] == []                                            # rows exist, so no auto fill...
    assert s["sources"]["soil"] == "real"
    st = client.get("/api/system/status").json()
    assert st["db"]["tables"]["soil"]["rows"] > 0 and st["camera"]["driver"] == "fake"


def test_images_path_safety_and_listing(client):
    assert client.get("/api/images/raw/../../etc/passwd").status_code == 404
    assert client.get("/api/images/raw/..%2F..%2Fconfig.json").status_code == 404
    assert client.get("/api/images/raw/config.json").status_code == 404
    assert client.get("/api/images?kind=raw").json()["files"] == []
    assert client.get("/api/images?kind=nope").status_code == 404


def test_camera_setup_flow_and_capture(client):
    st = client.get("/api/camera/status").json()
    assert st["driver"] == "fake" and st["all"] is False
    for name, body in [("autoroi", {"cols": 3, "rows": 2}), ("point", {"x": 100, "y": 360, "cm": 5}),
                       ("point", {"x": 400, "y": 360, "cm": 5}), ("setpot", {"pot_cm": 12}), ("auto", {}),
                       ("findleaf", {}), ("shuffle", {"seed": 3}), ("shoot", {})]:
        r = client.post(f"/api/camera/actions/{name}", json=body)
        assert r.status_code == 200, (name, r.text)
    st = client.get("/api/camera/status").json()
    assert st["all"] is True and st["mode"] == "random" and st["ppc"] > 0 and len(st["rois"]) == 6
    assert client.get("/api/camera/frame.jpg").headers["content-type"] == "image/jpeg"
    assert client.get("/api/camera/calib.jpg").status_code == 200
    assert client.post("/api/camera/actions/nope").status_code == 404
    r = client.post("/api/capture/run?phase=dawn&wait=1&warmup_s=0")
    j = r.json()["job"]
    assert r.status_code == 202 and j["state"] == "done" and j["ok_rows"] == 6 and j["published"] is False
    assert client.get("/api/capture/status").json()["last"]["state"] == "done"
    assert len(client.get("/api/capture/jobs").json()["jobs"]) == 1
    assert client.get(f"/api/capture/jobs/{j['id']}").json()["id"] == j["id"]
    assert client.get("/api/capture/jsonl").json()["lines"][0]["img"].startswith("fake_")
    sched = client.get("/api/capture/schedule").json()
    assert sched["dawn"] == "05:50" and sched["warmup_s"] == 0 and sched["next"]["phase"] in ("dawn", "pm")
    # setup actions are refused while a job holds the lock
    with client.app.state.ctx.camera.exclusive(label="job"):
        assert client.post("/api/camera/actions/findleaf").status_code == 409
    files = client.get("/api/images?kind=raw").json()["files"]
    assert files and files[0]["fake"] and client.get(files[0]["url"] + "?w=200").status_code == 200


def test_led_placeholder_and_config_write(client):
    assert client.get("/api/led").json()["installed"] is False
    assert client.post("/api/led/on").status_code == 409                # not installed -> explicit error
    assert client.post("/api/led/off").status_code == 200
    doc = client.get("/api/config").json()
    assert doc["config"]["led"]["driver"] == "noop"
    r = client.patch("/api/config", json={"layout": {"pot_cm": 11}}, headers={"if-match": str(doc["mtime"])})
    assert r.status_code == 200 and r.json()["config"]["layout"]["pot_cm"] == 11
    assert client.patch("/api/config", json={"layout": {"pot_cm": 12}}, headers={"if-match": "1"}).status_code == 409
    assert client.put("/api/config", json={"tz": "Nope/Zone"}).status_code == 422
    assert client.put("/api/config", json={"schedule": {"dawn": "99:99"}}).status_code == 422
    assert client.get("/api/config/check").json()["ok"] is False        # no rois yet
    assert client.get("/api/config/db-check").json()["mismatched_rows"] == 0


def test_ws_hello_and_spa_fallback(client):
    with client.websocket_connect("/ws") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "hello" and "dummy" in msg["data"]
        ws.send_json({"type": "ping"})
        assert ws.receive_json()["type"] == "pong"
    r = client.get("/")
    assert r.status_code == 200 and ("plantsvc" in r.text or "<div id=" in r.text)
    assert client.get("/api/nope").status_code == 404
