"""
setup_camera.py — 카메라 세팅을 이 파일 하나로 끝낸다.

  uv run python setup_camera.py            ->  http://rsp:8000  (폰으로 봐도 됩니다)

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
state  = {"msg": "준비됨", "pts": [], "ppc_fixed": None, "cm": 0, "order": None}


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

# ★ 미리보기와 촬영을 <하나의 설정>에서 뽑습니다.
#   예전에는 video_configuration(1280x720) 으로 보고 still_configuration(4608x2592)
#   으로 찍었는데, 두 설정은 센서 모드·ScalerCrop 이 달라 <화각이 어긋날 수 있습니다>.
#   그러면 SCALE = PREV[0]/CAP_W 라는 단순 비례가 깨지고, 화면에서 딱 맞게 그린
#   박스가 사진에서는 밀립니다. 실제로 그 일이 있었습니다.
#   lores 는 main 과 같은 ISP 출력에서 나오므로 화각이 같습니다 — 비례만 하면 됩니다.
#   모드 전환도 사라져서 '전환 직후 검은 띠' 문제도 없어집니다.
#   대가: 센서를 전체해상도로 계속 돌리므로 미리보기가 느립니다(수 fps).
#         설치용 도구라 감수할 만합니다.
try:
    still_cfg = cam.create_still_configuration(
        main={"size": (CAP_W, CAP_H)},
        lores={"size": PREV, "format": "RGB888"},
        buffer_count=2)
    cam.configure(still_cfg)
    PREV_STREAM = "lores"
except Exception as e:                    # 구버전 picamera2 는 lores 가 YUV420 만 됨
    print(f"[INFO] RGB888 lores 실패 ({e}) — YUV420 으로 재시도")
    still_cfg = cam.create_still_configuration(
        main={"size": (CAP_W, CAP_H)},
        lores={"size": PREV, "format": "YUV420"},
        buffer_count=2)
    cam.configure(still_cfg)
    PREV_STREAM = "lores_yuv"
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


stop_flag = threading.Event()      # Ctrl+C 때 grab 스레드를 세우는 신호


def preview_frame():
    """미리보기 한 장. lores 는 main 과 화각이 같으므로 SCALE 비례가 성립합니다.
    ★ lock 을 잡은 채로 부를 것 — 카메라는 한 번에 하나만 건드립니다."""
    if PREV_STREAM == "lores":
        return cam.capture_array("lores")
    a = cam.capture_array("lores")                       # YUV420
    return cv2.cvtColor(a, cv2.COLOR_YUV420p2BGR)


def grab():
    global latest
    while not stop_flag.is_set():          # Ctrl+C 가 오면 조용히 빠져나갑니다
        with lock:
            frame = preview_frame()
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


def act_setpot(cm):
    """화분 지름(cm)을 기록합니다. <자로 잰 값>입니다 — 이미지에서 유도하지 않습니다.

    배율(px/cm)은 두 점 클릭으로 정합니다. pot_cm 은 배율을 재는 값이 아니라,
    <잰 배율이 맞는지 검산하는 잣대>입니다. 그래서 측정과 독립이어야 합니다.
      · leaf_measure : 잎 면적이 화분 넓이의 절반도 안 되면 배율을 의심하라고 경고
      · check_config : ROI 가 화분의 1.5배 이상인지
      · 아래 act_point: 프레임 폭이 배치를 담을 만한지
    이미지에서 유도하면 위 검산에서 ppc 가 약분되어 배율이 틀려도 경고가 안 뜹니다.
    """
    if cm <= 0:
        return "0보다 큰 값을 넣으세요"
    CFG.setdefault("layout", {})["pot_cm"] = cm
    return f"화분 지름 {cm:g} cm 기록 — 배율 검산에 쓰입니다"


def act_shoot():
    """전체 해상도로 1장. 카메라를 놓지 않고 모드만 잠깐 바꿉니다.

    ★ 모드 전환 직후 바로 찍으면 센서가 프레임을 다 읽기 전이라
      사진 위쪽에 검은 띠가 남습니다. 전환 -> 대기 -> 버리는 컷 -> 촬영 순서로 갑니다.
    """
    # 모드 전환이 없어졌습니다 — main 스트림이 이미 전체해상도입니다.
    # 그래서 '전환 직후 검은 띠' 를 피하려던 대기·버리는 컷도 필요 없습니다.
    with lock:
        cam.capture_file("calib.jpg", name="main")
    return f"calib.jpg 저장 ({CAP_W}x{CAP_H})"


def _pack(boxes):
    """좌->우, 위->아래로 정렬해 p1..pN 이름을 붙이고 CFG 에 넣습니다.

    ★ 줄을 <고정 밴드>로 나누면 안 됩니다.
      한 줄로 놓은 화분도 세로로 조금 어긋나면 서로 다른 밴드에 떨어져
      좌우 순서가 뒤집힙니다. 그러면 p1 이 <다른 화분>을 가리키게 되고,
      과거 데이터의 p1 과 지금의 p1 이 달라집니다 — 조용히 실험을 망칩니다.
      그래서 <상자 높이>를 기준으로 같은 줄인지 판단합니다.
    """
    if not boxes:
        CFG["rois"] = []
        return
    hh  = sorted(b[3] for b in boxes)[len(boxes) // 2]     # 상자 높이의 중앙값
    tol = hh * 0.5                                          # 이만큼 안 벌어지면 같은 줄
    rows, cur = [], []
    for b in sorted(boxes, key=lambda b: b[1] + b[3] / 2):  # 중심 y 로 정렬
        if cur and (b[1] + b[3] / 2) - (cur[-1][1] + cur[-1][3] / 2) > tol:
            rows.append(cur); cur = []
        cur.append(b)
    rows.append(cur)
    boxes = [b for r in rows for b in sorted(r, key=lambda b: b[0])]  # 줄 안에서는 좌->우
    CFG["rois"] = [{"plant_id": f"p{i}", "treat": "",
                    "x": int(x), "y": int(y), "w": int(w), "h": int(h)}
                   for i, (x, y, w, h) in enumerate(boxes, 1)]


def _common_side():
    """지금 ROI 들이 <모두 같은 정사각형>이면 그 한 변을 돌려준다. 아니면 None."""
    rois = CFG.get("rois", [])
    if not rois:
        return None
    sides = {(int(r["w"]), int(r["h"])) for r in rois}
    if len(sides) != 1:
        return None
    w, h = sides.pop()
    return w if w == h else None


def _restore_treat(before):
    """자리만 옮긴 것이라면 처리군 배정을 되살린다.

    ★ 되살려도 되는 조건: 개수가 같고, <새 중심이 옛 박스 안>에 있을 것.
      화분이 옆자리로 넘어갔는데 배정을 그대로 두면 p1 이 다른 화분을 가리킨다 —
      데이터로는 구분되지 않고 실험이 조용히 뒤집힌다. 그럴 땐 비운다.
    """
    after = CFG.get("rois", [])
    if len(before) != len(after):
        return False
    for old, new_ in zip(before, after):
        cx, cy = new_["x"] + new_["w"] / 2, new_["y"] + new_["h"] / 2
        if not (old["x"] <= cx <= old["x"] + old["w"] and
                old["y"] <= cy <= old["y"] + old["h"]):
            return False
    for old, new_ in zip(before, after):
        new_["treat"] = old.get("treat", "")
    return True


def act_findleaf(expand=1.8):
    """★ 잎을 찾아 박스의 <중심만> 옮깁니다. 크기는 바꾸지 않습니다.

    예전에는 side = max(잎 가로, 잎 세로) * expand 로 <잎 크기에 비례해> 박스를
    만들었습니다. 그러면 잎이 작은 화분이 영구히 작은 박스를 갖고, 그 화분은
    어느 한 처리군에 속하므로 <잘림이 처리군과 정렬>됩니다. 캐노피가 박스를
    넘으면 작은 쪽이 먼저 잘리고, 잘린 면적과 실제로 작은 면적은 데이터상
    구분되지 않습니다. 그래서 크기는 건드리지 않습니다.

    이미 ROI 가 있으면 그 크기를 그대로 쓰고, 없으면 잎 중 가장 큰 것에 맞춰
    <모두 같은 크기>로 만듭니다.
    """
    with lock:
        frame = preview_frame()
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
    # ★ 크기뿐 아니라 <실제로 초록인지>도 봅니다.
    #   NORM_MINMAX + Otsu 는 무엇이 들어오든 반드시 둘로 가르므로, 잎이 없어도
    #   '가장 초록스러운 쪽'을 만들어냅니다. 어두운 구석의 잡음이 그렇게 잡혔습니다.
    #   중성 회색의 정규화 ExG 는 0, 초록 잎은 0.2~0.4 입니다.
    blobs = [i for i in range(1, n)
             if st[i, cv2.CC_STAT_AREA] > 0.005 * pw * ph
             and float(exg[lab == i].mean()) > 0.06]
    if not blobs:
        return "초록 덩어리를 못 찾았습니다 — 조명·초점을 먼저 맞추세요"

    keep = _common_side()                      # 촬영 좌표계의 한 변
    if keep:
        side = keep * SCALE                    # 미리보기 좌표로
        how = f"기존 크기 {keep}px 유지"
    else:
        side = max(max(st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT])
                   for i in blobs) * expand    # 가장 큰 잎 기준 — 전부 같은 크기
        how = "새 크기(가장 큰 잎 기준) · 전부 동일"

    boxes = [[cen[i][0] - side / 2, cen[i][1] - side / 2, side, side] for i in blobs]

    for _ in range(12):                        # 겹치면 <다같이> 줄입니다 — 크기는 계속 같습니다
        over = any(
            min(a[0]+a[2], c[0]+c[2]) - max(a[0], c[0]) > 0 and
            min(a[1]+a[3], c[1]+c[3]) - max(a[1], c[1]) > 0
            for i, a in enumerate(boxes) for c in boxes[i+1:])
        if not over:
            break
        side *= 0.90
        boxes = [[cen[i][0] - side / 2, cen[i][1] - side / 2, side, side] for i in blobs]
        how += " (겹쳐서 축소)"

    out = []
    for x, y, w, h in boxes:                   # 미리보기 -> 촬영 좌표 + 프레임 안으로
        X, Y, W_, H_ = x / SCALE, y / SCALE, w / SCALE, h / SCALE
        W_ = min(W_, CAP_W); H_ = min(H_, CAP_H)
        X = max(0, min(X, CAP_W - W_)); Y = max(0, min(Y, CAP_H - H_))
        out.append((X, Y, W_, H_))

    before = [dict(r) for r in CFG.get("rois", [])]
    _pack(out)
    kept = _restore_treat(before)

    sides = {r["w"] for r in CFG["rois"]}
    same = "모두 같음" if len(sides) == 1 else f"★ 다름 {sides}"
    tail = "처리군 유지됨" if kept else "처리군이 비었습니다 — 다시 배정하세요"
    return (f"잎 {len(out)}개 — 중심만 이동 · {how} · 크기 {same} · {tail}")


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


def act_rename():
    """이름 다시 매기기 — 원하는 순서대로 화면의 박스를 클릭하게 합니다.
    자동 정렬이 어떻게 하든, <사람이 정한 순서>가 이깁니다."""
    n = len(CFG.get("rois", []))
    if n == 0:
        return "ROI 가 없습니다 — 먼저 배치하세요"
    state["order"] = []
    return f"이름을 붙일 순서대로 화면의 박스를 클릭하세요 (0/{n})"


def act_pickroi(x, y):
    """이름 매기기 중의 클릭 — 어느 박스를 골랐는지 찾아 순서에 담습니다."""
    if state["order"] is None:
        return "먼저 [이름 다시 매기기] 를 누르세요"
    X, Y = x / SCALE, y / SCALE                       # 미리보기 -> 촬영 좌표
    hit = [i for i, r in enumerate(CFG["rois"])
           if r["x"] <= X <= r["x"] + r["w"] and r["y"] <= Y <= r["y"] + r["h"]]
    if not hit:
        return "박스 안을 클릭하세요"
    i = hit[0]
    if i in state["order"]:
        return "이미 고른 박스입니다"
    state["order"].append(i)

    n = len(CFG["rois"])
    if len(state["order"]) < n:
        return f"{len(state['order'])}/{n} — 다음 박스를 클릭하세요"

    # 다 골랐습니다. 고른 순서대로 이름을 새로 붙입니다 (처리군은 박스를 따라갑니다)
    CFG["rois"] = [dict(CFG["rois"][i], plant_id=f"p{k}")
                   for k, i in enumerate(state["order"], 1)]
    state["order"] = None
    return "이름 지정 완료 — " + " · ".join(
        f"{r['plant_id']}(x={r['x']})" for r in CFG["rois"])


def act_settreat(pid, treat):
    """사람이 직접 지정. 이미 펌프를 꽂아둔 상황을 위한 길입니다.
    ★ 무작위가 아니므로 <어떻게 정했는지>를 config 에 남깁니다 —
      보고서에 '무작위 배정' 이라고 쓸 수 있는지가 여기서 갈립니다."""
    if treat not in ("stable", "fluct"):
        return f"알 수 없는 처리군: {treat}"
    hit = [r for r in CFG.get("rois", []) if r["plant_id"] == pid]
    if not hit:
        return f"{pid} 를 찾을 수 없습니다"
    hit[0]["treat"] = treat
    CFG["treat_mode"] = "manual"
    return f"{pid} → {treat} (직접 지정)"


def act_shuffle():
    CFG["treat_mode"] = "random"
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
            "mode": CFG.get("treat_mode", ""),
            "naming": state["order"] is not None,
            "pots": [{"id": r["plant_id"], "treat": r.get("treat", "")}
                     for r in CFG.get("rois", [])],
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
    "setpot":  lambda p: act_setpot(float(p.get("pot_cm", 10))),
    "shuffle": lambda p: act_shuffle(),
    "settreat":lambda p: act_settreat(p["pid"], p["treat"]),
    "rename":  lambda p: act_rename(),
    "pickroi": lambda p: act_pickroi(float(p["x"]), float(p["y"])),
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
 .pot{display:flex;align-items:center;gap:5px;margin:5px 0;font-size:var(--fs)}
 .pot b{flex:0 0 30px}
 .pot button{flex:1;margin:0;padding:5px 0;font-size:12px;background:#39424e}
 .pot button.on{background:var(--c)}
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
    <div class="row" style="margin-top:8px">화분 지름 <input id="potcm" value="10"> cm
      <button class="sub" onclick="go('setpot',{pot_cm:potcm.value})">기록</button></div>
    <div class="echo">자로 잰 값 — 배율을 <b>검산</b>하는 데 씁니다</div>
  </div>

  <div class="step" id="k-roi" style="--c:var(--s3)">
    <div class="hd"><span class="no"><span>3</span></span>ROI</div>
    <button onclick="go('findleaf')">잎 찾아 배치</button>
    <div class="row">열 <input id="c" value="2"> 행 <input id="r" value="1"></div>
    <button class="sub" onclick="go('autoroi',{cols:c.value,rows:r.value})">격자로 나누기</button>
    <button class="sub" id="rnBtn" onclick="go('rename')">이름 다시 매기기</button>
    <div class="echo" id="rnEcho"></div>
  </div>

  <div class="step" id="k-treat" style="--c:var(--s4)">
    <div class="hd"><span class="no"><span>4</span></span>처리군</div>
    <button onclick="go('shuffle')">무작위 배정</button>
    <div id="pots"></div>
    <div class="echo" id="modeEcho"></div>
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

  document.getElementById('pots').innerHTML = (st.pots || []).map(p =>
    `<div class="pot"><b>${p.id}</b>` +
    `<button class="${p.treat === 'stable' ? 'on' : ''}" ` +
    `onclick="go('settreat',{pid:'${p.id}',treat:'stable'})">꾸준</button>` +
    `<button class="${p.treat === 'fluct' ? 'on' : ''}" ` +
    `onclick="go('settreat',{pid:'${p.id}',treat:'fluct'})">널뜀</button></div>`).join('');
  naming = !!st.naming;
  document.getElementById('rnBtn').textContent =
    naming ? '고르는 중 — 새로고침하면 취소' : '이름 다시 매기기';
  document.getElementById('rnEcho').innerHTML = naming
    ? '<b style="color:#8E6FBF">원하는 순서대로 화면의 박스를 클릭하세요</b>'
    : '자동 순서가 마음에 안 들면 직접 지정하세요';

  const MODE = {random: '무작위로 배정됨 — 보고서에 &ldquo;무작위 배정&rdquo; 이라 쓸 수 있습니다',
                manual: '<b style="color:#D2694F">직접 지정됨 — 무작위가 아닙니다</b>'};
  document.getElementById('modeEcho').innerHTML = MODE[st.mode] || '아직 배정하지 않았습니다';
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
let naming = false;
document.getElementById('im').addEventListener('click', e => {
  const r = e.target.getBoundingClientRect();
  const x = (e.clientX-r.left)/r.width*1280, y = (e.clientY-r.top)/r.height*720;
  // 이름 매기는 중에는 <배율 클릭>이 아니라 <박스 고르기>가 됩니다
  if (naming) go('pickroi', { x, y });
  else        go('point',   { x, y, cm: document.getElementById('cm').value });
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
    print(f"http://<pi-ip>:{PORT}   또는   http://rsp:{PORT}")
    print("끝나면 Ctrl+C — 켜둔 채로 두면 run_capture.py 가 카메라를 못 잡습니다.")
    try:
        S(("", PORT), H).serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다 —", end=" ", flush=True)
    finally:
        # ★ grab 스레드를 먼저 세운 뒤 카메라를 놓습니다.
        #   순서가 반대면 스레드가 닫힌 카메라를 건드려 오류가 납니다.
        stop_flag.set()
        time.sleep(0.2)
        try:
            cam.stop(); cam.close()
            print("카메라를 놓았습니다. 이제 run_capture.py 가 쓸 수 있습니다.")
        except Exception as e:
            print(f"카메라 정리 중 문제: {e}")
            print("  확인:  pgrep -af setup_camera.py ; sudo fuser -v /dev/media0")
