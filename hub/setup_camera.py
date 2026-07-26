"""
setup_camera.py — 카메라 세팅을 이 파일 하나로 끝낸다.

  uv run python setup_camera.py            ->  http://rasp:8000  (폰으로 봐도 됩니다)

  ① 노출·초점 자동 측정 후 고정   ② 두 점 클릭으로 배율
  ③ 잎을 찾아 ROI 배치           ④ 처리군 무작위 배정
  ⑤ 기준 사진 calib.jpg (마지막에 한 번)

★ ArUco 마커를 쓰지 않습니다.
  배율 — 화면에서 두 점을 클릭해 한 번 정합니다.
  위치 감시 — frame_align.py 가 기준 사진과 비교해 밀림·회전·배율 변화를 잡습니다.
  인쇄·코팅·부착·6주 관리가 사라지는 대신, <카메라를 단단히 고정>하는 것이 전제입니다.

★ 이 스크립트가 카메라를 계속 쥐고 있습니다. 촬영할 때도 놓지 않으므로
  화각을 몇 번을 다시 잡든 'Device or resource busy' 가 나지 않습니다.
  다 끝나면 Ctrl+C — 켜둔 채 두면 run_capture.py 가 실패합니다.
"""
import io, json, os, random, socketserver, threading, time
from http import server

import cv2
import numpy as np
from picamera2 import Picamera2
from libcamera import controls

CFG_PATH = "config.json"
PORT     = 8000
PREV     = (1280, 720)          # 미리보기 해상도 (화면용)

lock   = threading.Lock()       # 카메라는 한 번에 하나만 건드립니다
latest = None                   # 최신 JPEG 프레임
state  = {"msg": "준비됨", "pts": [], "ppc_fixed": None, "cm": 0}


def load_cfg():
    with open(CFG_PATH) as f:
        return json.load(f)


def save_cfg(cfg):
    with open(CFG_PATH, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


CFG   = load_cfg()
CAP   = CFG["capture"]
CAP_W, CAP_H = CAP["size"]
SCALE = PREV[0] / CAP_W         # 촬영 좌표 -> 미리보기 좌표

# ══════════════ 카메라 ══════════════
cam = Picamera2()
video_cfg = cam.create_video_configuration(main={"size": PREV, "format": "RGB888"})
still_cfg = cam.create_still_configuration(main={"size": (CAP_W, CAP_H)})
cam.configure(video_cfg)
cam.start()
cam.set_controls({                                   # 촬영과 동일한 고정 설정
    "AfMode": controls.AfModeEnum.Manual, "LensPosition": CAP["lens_position"],
    "AeEnable": False, "ExposureTime": CAP["exposure_us"], "AnalogueGain": CAP["gain"],
    "AwbEnable": False, "ColourGains": tuple(CAP["colour_gains"]),
})
time.sleep(2)


def draw(img):
    h, w = img.shape[:2]

    # 프레임 안전선 — 이 안쪽이면 여유 있음
    m = int(min(w, h) * 0.05)
    cv2.rectangle(img, (m, m), (w - m, h - m), (150, 150, 150), 1)

    # ROI 박스 (촬영 좌표 -> 미리보기 좌표)
    for r in CFG.get("rois", []):
        x, y = int(r["x"] * SCALE), int(r["y"] * SCALE)
        ww, hh = int(r["w"] * SCALE), int(r["h"] * SCALE)
        out = x < 0 or y < 0 or x + ww > w or y + hh > h
        col = (0, 0, 255) if out else (255, 170, 0)
        cv2.rectangle(img, (x, y), (x + ww, y + hh), col, 2)
        tag = f'{r["plant_id"]} {r.get("treat") or "?"}'
        cv2.putText(img, tag, (x + 6, y + 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
        if out:
            cv2.putText(img, "OUT OF FRAME", (x + 6, y + 48),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)

    # 배율 측정용 두 점
    for i, (px, py) in enumerate(state["pts"]):
        cv2.circle(img, (int(px), int(py)), 7, (0, 255, 255), -1)
    if len(state["pts"]) == 2:
        a, b = [(int(p[0]), int(p[1])) for p in state["pts"]]
        cv2.line(img, a, b, (0, 255, 255), 2)

    # 하단 상태바
    cv2.rectangle(img, (0, h - 34), (w, h), (0, 0, 0), -1)
    ppc = f'{state["ppc_fixed"]:.1f} px/cm' if state["ppc_fixed"] else 'px/cm --'
    cv2.putText(img, f'{ppc}    ROI {len(CFG.get("rois", []))}',
                (10, h - 11), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 2)
    return img


def grab():
    global latest
    while True:
        with lock:
            frame = cam.capture_array()
        frame = draw(frame)
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            latest = buf.tobytes()
        time.sleep(0.08)


# ══════════════ 동작 ══════════════
def act_point(x, y, cm):
    """화면에서 찍은 두 점 사이 거리로 배율을 구합니다. 마커가 없을 때 쓰는 자(尺).
    화분 지름처럼 <잎과 비슷한 높이>의 길이를 쓰는 것이 원근 오차가 적습니다."""
    pts = state["pts"]
    if len(pts) >= 2:
        pts = []
    pts.append([x, y])
    state["pts"] = pts
    if len(pts) < 2:
        return "첫 점 찍음 — 반대쪽 끝을 한 번 더 클릭하세요"

    d_prev = float(np.hypot(pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]))
    d_cap  = d_prev / SCALE                       # 미리보기 -> 촬영 좌표
    if cm <= 0 or d_cap <= 0:
        return "길이가 0입니다"
    ppc = d_cap / cm
    state["ppc_fixed"] = ppc
    state["cm"] = cm
    CFG.setdefault("qc", {})["px_per_cm_ref"] = round(ppc, 1)
    # 검산 — 프레임 폭이 화분 배치와 말이 되는가.  클릭 실수를 여기서 잡습니다.
    frame_cm = CAP_W / ppc
    lay = CFG.get("layout", {})
    pot = float(lay.get("pot_cm", 0) or 0)
    need = int(lay.get("cols", 1)) * pot + (int(lay.get("cols", 1)) - 1) * float(lay.get("gap_cm", 0) or 0)
    warn = ""
    if pot and frame_cm < need:
        warn = f"   ⚠ 프레임 폭 {frame_cm:.0f}cm 가 배치 {need:.0f}cm 보다 좁습니다 — 다시 재세요"
    elif pot and frame_cm > need * 3:
        warn = f"   ⚠ 프레임 폭 {frame_cm:.0f}cm 는 배치 {need:.0f}cm 의 3배가 넘습니다 — 길이 입력칸을 확인하세요"
    return (f"{d_cap:.0f}px(원본) / {cm:g}cm  ->  {ppc:.1f} px/cm"
            f"  · 프레임 폭 {frame_cm:.0f}cm{warn}")


def act_shoot():
    """전체 해상도로 1장. 카메라를 놓지 않고 모드만 잠깐 바꿉니다.

    ★ 모드 전환 직후 바로 찍으면 센서가 프레임을 다 읽기 전이라
      사진 위쪽에 검은 띠가 남습니다. 전환 -> 대기 -> 버리는 컷 -> 촬영 순서로 갑니다.
    """
    with lock:
        cam.switch_mode(still_cfg)
        time.sleep(0.7)                       # 센서·ISP 안정화
        cam.capture_array()                   # 첫 컷은 버립니다
        cam.capture_file("calib.jpg")
        cam.switch_mode(video_cfg)
        time.sleep(0.3)
    return f"calib.jpg 저장 ({CAP_W}x{CAP_H})"


def _pack(boxes):
    """좌->우, 위->아래로 정렬해 p1..pN 이름을 붙이고 CFG 에 넣습니다."""
    boxes.sort(key=lambda b: (b[1] // max(1, CAP_H // 8), b[0]))
    CFG["rois"] = [{"plant_id": f"p{i}", "treat": "",
                    "x": int(x), "y": int(y), "w": int(w), "h": int(h)}
                   for i, (x, y, w, h) in enumerate(boxes, 1)]


def act_findleaf(expand=1.8):
    """★ 진짜 자동 — 잎을 찾아 그 자리에 박스를 놓습니다.
    측정에 쓰는 것과 <같은 ExG> 로 초록을 찾으므로, 여기서 잡히면 측정도 잡힙니다."""
    with lock:
        frame = cam.capture_array()
    b, g, r = cv2.split(frame.astype(np.float32))       # BGR 배열
    ssum = b + g + r + 1e-6
    exg = 2 * (g / ssum) - (r / ssum) - (b / ssum)
    x8 = cv2.normalize(exg, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    x8 = cv2.GaussianBlur(x8, (7, 7), 0)
    _, m = cv2.threshold(x8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k, iterations=2)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k, iterations=1)

    n, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
    ph, pw = m.shape
    blobs = [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] > 0.005 * pw * ph]
    if not blobs:
        return "초록 덩어리를 못 찾았습니다 — 조명·초점을 먼저 맞추세요"

    boxes = []
    for i in blobs:
        cx, cy = cen[i]
        side = max(st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT]) * expand
        boxes.append([cx - side / 2, cy - side / 2, side, side])

    for _ in range(12):                                  # 겹치면 조금씩 줄입니다
        over = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, c = boxes[i], boxes[j]
                if (min(a[0]+a[2], c[0]+c[2]) - max(a[0], c[0]) > 0 and
                    min(a[1]+a[3], c[1]+c[3]) - max(a[1], c[1]) > 0):
                    over = True
        if not over:
            break
        for bx in boxes:
            bx[0] += bx[2] * 0.05; bx[1] += bx[3] * 0.05
            bx[2] *= 0.90; bx[3] *= 0.90

    out = []
    for x, y, w, h in boxes:                             # 미리보기 -> 촬영 좌표 + 프레임 안으로
        X, Y, W_, H_ = x / SCALE, y / SCALE, w / SCALE, h / SCALE
        X = max(0, min(X, CAP_W - W_)); Y = max(0, min(Y, CAP_H - H_))
        W_ = min(W_, CAP_W); H_ = min(H_, CAP_H)
        out.append((X, Y, W_, H_))
    _pack(out)
    return f"잎 덩어리 {len(out)}개를 찾아 ROI 를 배치했습니다 — 화면에서 확인하세요"


def act_autoroi(cols, rows, margin=0.04):
    """프레임을 cols x rows 격자로 나눕니다(칸 수는 사람이 지정).
    treat 는 비워 둡니다 — 위치와 처리를 묶지 않기 위해."""
    mx, my = int(CAP_W * margin), int(CAP_H * margin)
    cw = (CAP_W - 2 * mx) // cols
    ch = (CAP_H - 2 * my) // rows
    side = int(min(cw, ch) * 0.92)
    rois = []
    n = 1
    for r in range(rows):
        for c in range(cols):
            cx = mx + cw * c + cw // 2
            cy = my + ch * r + ch // 2
            rois.append({"plant_id": f"p{n}", "treat": "",
                         "x": cx - side // 2, "y": cy - side // 2,
                         "w": side, "h": side})
            n += 1
    CFG["rois"] = rois
    return f"{cols}x{rows} 격자 = {len(rois)}칸 — 처리군은 아직 비어 있습니다"


def act_auto():
    """카메라에게 한 번 자동으로 맞춰보게 한 뒤, 그 값을 읽어 <고정>합니다.
    화면이 새까맣거나 하얗게 날아갈 때 이걸 먼저 누르세요."""
    with lock:
        cam.set_controls({"AeEnable": True, "AwbEnable": True,
                          "AfMode": controls.AfModeEnum.Auto})
    time.sleep(3)                                   # 노출·화이트밸런스 수렴 대기
    try:                                            # ★ AfMode 만 켜면 초점은 안 움직입니다.
        with lock:                                  #   스캔을 <직접> 돌려야 합니다.
            cam.autofocus_cycle()
    except Exception:
        pass
    time.sleep(1)
    with lock:
        m = cam.capture_metadata()
        exp  = int(m.get("ExposureTime", CAP["exposure_us"]))
        gain = float(m.get("AnalogueGain", CAP["gain"]))
        cg   = m.get("ColourGains", CAP["colour_gains"])
        lens = float(m.get("LensPosition", CAP["lens_position"]))
        cam.set_controls({                          # 다시 전부 수동으로 잠급니다
            "AeEnable": False, "ExposureTime": exp, "AnalogueGain": gain,
            "AwbEnable": False, "ColourGains": (float(cg[0]), float(cg[1])),
            "AfMode": controls.AfModeEnum.Manual, "LensPosition": lens})
    CAP["exposure_us"]   = exp                      # CAP 은 CFG["capture"] 자체
    CAP["gain"]          = round(gain, 2)
    CAP["colour_gains"]  = [round(float(cg[0]), 2), round(float(cg[1]), 2)]
    CAP["lens_position"] = round(lens, 2)
    warn = ""
    if gain > 4.0:
        warn = f"  ⚠ gain {gain:.1f} 은 높습니다 — 조명을 밝게 하고 다시 측정하세요(노이즈)"
    elif gain > 2.0:
        warn = "  · 조명을 더 밝게 하면 노이즈가 줄어듭니다"
    return (f"exp {exp} · gain {gain:.2f} · WB {cg[0]:.2f}/{cg[1]:.2f} · lens {lens:.2f}"
            f"  —  [저장] 을 눌러야 config.json 에 기록됩니다{warn}")


def act_shuffle():
    """제비뽑기. 위치와 무관하게 stable/fluct 를 섞습니다."""
    rois = CFG.get("rois", [])
    n = len(rois)
    if n == 0:
        return "ROI 가 없습니다"
    if n % 2:
        return f"ROI 가 {n}개(홀수)라 반씩 나눌 수 없습니다"
    labels = ["stable"] * (n // 2) + ["fluct"] * (n // 2)
    random.shuffle(labels)
    for r, t in zip(rois, labels):
        r["treat"] = t
    return "무작위 배정 완료 — " + " ".join(f'{r["plant_id"]}:{r["treat"][0]}' for r in rois)


def persist():
    """★ 모든 동작 뒤에 자동 호출. 버튼을 눌러도 파일에 안 쓰이는 사고를 없앱니다."""
    save_cfg(CFG)


def step_done():
    """단계별 완료 여부 — 화면 왼쪽 패널이 이 값으로 색을 칠합니다."""
    rois = CFG.get("rois", [])
    return {
        "focus": bool(CAP.get("lens_position") and CAP.get("exposure_us")),
        "scale": bool(float(CFG.get("qc", {}).get("px_per_cm_ref", 0) or 0)),
        "roi":   bool(rois),
        "treat": bool(rois) and not [r for r in rois
                                     if r.get("treat") not in ("stable", "fluct")],
        "shot":  os.path.exists("calib.jpg"),
    }


def status():
    d = step_done()
    return {"msg": state["msg"], "done": d, "all": all(d.values()),
            "ppc": round(state["ppc_fixed"] or 0, 1),
            "nroi": len(CFG.get("rois", [])),
            "cm": float(state.get("cm") or 0)}


def act_save():
    return "현재 설정을 다시 저장했습니다"


ACTIONS = {
    "shoot":   lambda p: act_shoot(),
    "autoroi": lambda p: act_autoroi(int(p.get("cols", 3)), int(p.get("rows", 2))),
    "findleaf":lambda p: act_findleaf(),
    "auto":    lambda p: act_auto(),
    "point":   lambda p: act_point(float(p["x"]), float(p["y"]), float(p.get("cm", 10))),
    "shuffle": lambda p: act_shuffle(),
    "save":    lambda p: act_save(),
}

PAGE = """<!doctype html><meta charset="utf-8">
<title>camera setup</title>
<style>
 :root{
   --bg:#111418; --card:#1a1f26; --line:#2b323c; --ink:#e8ecf1; --dim:#8d97a3;
   --s1:#3E7CB1; --s2:#2F9E7E; --s3:#8E6FBF; --s4:#D2694F; --s5:#5B8C4A; --ok:#3f9d5a;
   --fs:13px;
 }
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--ink);
      font:var(--fs)/1.55 system-ui,'Malgun Gothic',sans-serif;
      display:flex;gap:16px;padding:16px;align-items:flex-start}

 /* 왼쪽 — 조작만 */
 #panel{flex:0 0 236px;display:flex;flex-direction:column;gap:8px}
 .step{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--c);
       border-radius:8px;padding:9px 11px}
 .step.done{border-left-color:var(--ok)}
 .step .hd{display:flex;align-items:center;gap:8px;font-weight:700;font-size:var(--fs);
           margin-bottom:7px}
 .step .no{flex:0 0 20px;height:20px;border-radius:50%;background:var(--c);color:#fff;
           display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700}
 .step.done .no{background:var(--ok)}
 .step.done .no::after{content:'✓'}
 .step.done .no span{display:none}
 button{width:100%;padding:9px;margin:3px 0;border:0;border-radius:6px;background:var(--c);
        color:#fff;font:700 var(--fs)/1.2 inherit;cursor:pointer}
 button.sub{background:#39424e}
 button:active{transform:translateY(1px)}
 .row{display:flex;align-items:center;gap:6px;margin:2px 0;font-size:var(--fs)}
 input{width:56px;padding:5px 6px;border-radius:5px;border:1px solid var(--line);
        background:#0d1116;color:var(--ink);font:var(--fs) inherit;text-align:center}
 .echo{font-size:var(--fs);color:var(--dim);margin-top:4px}
 .echo b{color:var(--ink)}

 /* 오른쪽 — 영상 + 설명 */
 #right{flex:1;min-width:0;display:flex;flex-direction:column;gap:10px}
 #right img{width:100%;max-width:1000px;display:block;border-radius:8px;border:1px solid var(--line)}
 .info{background:var(--card);border:1px solid var(--line);border-radius:8px;
       padding:11px 14px;max-width:1000px}
 .info h4{margin:0 0 6px;font-size:var(--fs);color:var(--dim);font-weight:700;
          letter-spacing:.04em}
 .info ul{margin:0;padding-left:17px}
 .info li{margin:3px 0;font-size:var(--fs)}
 .info li b{color:#fff}
 #msg{background:#0d1116;border:1px solid var(--line);border-radius:8px;padding:10px 14px;
      max-width:1000px;font-size:var(--fs);min-height:40px}
 #msg.warn{border-color:#8a5a2b;background:#241a10}
 #msg.good{border-color:#2f6b40;background:#101d14}
</style>

<div id="panel">
  <div class="step" id="k-focus" style="--c:var(--s1)">
    <div class="hd"><span class="no"><span>1</span></span>노출 · 초점</div>
    <button onclick="go('auto')">자동 측정 → 고정</button>
  </div>

  <div class="step" id="k-scale" style="--c:var(--s2)">
    <div class="hd"><span class="no"><span>2</span></span>배율</div>
    <div class="row">길이 <input id="cm" value="5" oninput="echo()"> cm</div>
    <div class="echo" id="cmEcho"></div>
  </div>

  <div class="step" id="k-roi" style="--c:var(--s3)">
    <div class="hd"><span class="no"><span>3</span></span>ROI</div>
    <button onclick="go('findleaf')">잎 찾아 배치</button>
    <div class="row">열 <input id="c" value="2"> 행 <input id="r" value="1"></div>
    <button class="sub" onclick="go('autoroi',{cols:c.value,rows:r.value})">격자로 나누기</button>
  </div>

  <div class="step" id="k-treat" style="--c:var(--s4)">
    <div class="hd"><span class="no"><span>4</span></span>처리군</div>
    <button onclick="go('shuffle')">무작위 배정</button>
  </div>

  <div class="step" id="k-shot" style="--c:var(--s5)">
    <div class="hd"><span class="no"><span>5</span></span>기준 사진</div>
    <button onclick="go('shoot')">촬영 — calib.jpg</button>
  </div>

  <button class="sub" onclick="go('save')">상태 다시 확인</button>
</div>

<div id="right">
  <img id="im" src="/stream.mjpg">
  <div id="msg">준비됨</div>
  <div class="info">
    <h4>순서대로</h4>
    <ul>
      <li><b>1 노출·초점</b> — 카메라를 고정한 뒤 누릅니다. gain 이 2 이하가 되도록 조명을 보태세요</li>
      <li><b>2 배율</b> — 길이를 <b>먼저</b> 입력 &rarr; 화면에서 두 점 클릭. 클릭 뒤 숫자를 바꿔도 반영 안 됨</li>
      <li style="color:#8d97a3">· 자·격자처럼 눈금이 또렷한 것을 쓰세요. 화분 테두리는 잎에 가려 부정확합니다</li>
      <li style="color:#8d97a3">· 도트 격자는 한 칸 1cm — <b>5cm 는 간격 5칸(점 6개)</b></li>
      <li><b>3 ROI</b> — 잎 덩어리를 찾아 박스를 놓습니다. 개수가 맞지 않으면 격자로</li>
      <li><b>4 처리군</b> — ROI 를 다시 만들면 배정이 지워지므로 <b>반드시 3 다음</b></li>
      <li><b>5 기준 사진</b> — 전부 끝난 뒤 <b>한 번만</b>. 6주간 밀림 판정의 기준이 됩니다</li>
      <li style="color:#8d97a3">· 끝나면 <b>Ctrl+C</b> — 켜둔 채 두면 자동 촬영이 카메라를 못 잡습니다</li>
    </ul>
  </div>
</div>

<script>
function echo(){
  const v = parseFloat(document.getElementById('cm').value);
  document.getElementById('cmEcho').innerHTML =
    (v > 0) ? '두 점 사이를 <b>' + v + ' cm</b> 로 계산합니다'
            : '<b style="color:#d2694f">길이를 입력하세요</b>';
}
function paint(st){
  for (const [k, v] of Object.entries(st.done))
    document.getElementById('k-' + k).classList.toggle('done', v);
  const m = document.getElementById('msg');
  m.textContent = st.msg + (st.all ? '   ✓ 모든 단계 완료' : '');
  m.className = st.all ? 'good' : (/⚠|실패|주의/.test(st.msg) ? 'warn' : '');
}
async function go(a, p={}){
  document.getElementById('msg').textContent = '처리 중...';
  if (a === 'point' || a === 'auto' || a === 'shoot') { /* 그대로 */ }
  const q = new URLSearchParams(p).toString();
  const res = await fetch('/do/' + a + (q ? '?' + q : ''), {method:'POST'});
  paint(await res.json());
}
document.getElementById('im').addEventListener('click', e => {
  const r = e.target.getBoundingClientRect();
  go('point', { x:(e.clientX-r.left)/r.width*1280,
                y:(e.clientY-r.top)/r.height*720,
                cm: document.getElementById('cm').value });
});
echo();
fetch('/status').then(r => r.json()).then(paint);
</script>"""


class H(server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        # 예전 mjpeg.py 주소(/index.html)로 들어와도 받아줍니다 — 브라우저가 기억하고 있습니다
        if self.path in ("/", "/index.html"):
            b = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(b))
            self.end_headers()
            self.wfile.write(b)
        elif self.path == "/status":
            self._json(status()); return
        elif self.path == "/stream.mjpg":
            self.send_response(200)
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=FRAME")
            self.end_headers()
            try:
                while True:
                    if latest:
                        self.wfile.write(b"--FRAME\r\nContent-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(latest)}\r\n\r\n".encode())
                        self.wfile.write(latest)
                        self.wfile.write(b"\r\n")
                    time.sleep(0.08)
            except Exception:
                pass
        else:
            self.send_response(302)          # 나머지는 전부 첫 화면으로
            self.send_header("Location", "/")
            self.end_headers()

    def _json(self, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(b))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        name, _, query = self.path[4:].partition("?")
        params = dict(p.split("=") for p in query.split("&") if "=" in p)
        try:
            msg = ACTIONS[name](params)
            persist()                                   # ★ 누를 때마다 파일에 기록
        except KeyError:
            self.send_error(404); return
        except Exception as e:
            msg = f"실패: {e}"
        state["msg"] = msg
        self._json(status())


class S(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    threading.Thread(target=grab, daemon=True).start()
    print(f"http://<pi-ip>:{PORT}   또는   http://rasp:{PORT}")
    print("끝나면 Ctrl+C — 켜둔 채로 두면 run_capture.py 가 카메라를 못 잡습니다.")
    try:
        S(("", PORT), H).serve_forever()
    finally:
        cam.stop()
        cam.close()
