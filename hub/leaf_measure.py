"""
leaf_measure.py — 사진 1장 -> 화분별 캐노피 투영면적.  라이브러리(직접 실행하지 않음).

  쓰는 쪽      run_capture.py 가  import leaf_measure  후  measure(...) 호출
  단독 점검    uv run python leaf_measure.py photos/raw/xxx.jpg

파이프라인
  ① frame_align   기준 사진 대비 밀림을 재고 ROI 를 옮김
  ② ROI 로 자름    화분 하나씩
  ③ ExG           2g − r − b.  <정규화> 라 밝기 변화에 둔감
  ④ Otsu          임계값을 사진마다 스스로 정함
  ⑤ 형태학        점 제거(open) → 구멍 메움(close)
  ⑥ 최대 덩어리    흙의 녹조·옆 화분 잎 같은 흩어진 초록을 버림
  ⑦ 면적·윤곽      area_px, area_cm2, contour(중심 기준 좌표)

★ 투영 캐노피 면적 ≠ 잎 면적.  겹친 잎은 한 번만 세므로 <항상 과소평가>입니다.
  생장률 비교에는 충분하지만, 보고서에는 "투영 캐노피 면적"으로 쓰고
  6주차 파괴 측정(실제 잎면적·건중량·뿌리)으로 검증하세요.
"""
import json, os, sys
import cv2
import numpy as np

try:
    import frame_align
except ImportError:                      # 없으면 밀림 보정만 건너뜁니다
    frame_align = None

CFG_PATH = "config.json"
REF_PATH = "calib.jpg"


def cfg():
    return json.load(open(CFG_PATH))


# ══════════════ ③~⑥ 잎 분리 ══════════════
def leaf_mask(bgr, ksize=5, open_it=1, close_it=2):
    """ROI 한 칸 안에서 잎만 남긴 흑백 마스크와 픽셀 수."""
    b, g, r = cv2.split(bgr.astype(np.float32))
    s = b + g + r + 1e-6
    exg = 2 * (g / s) - (r / s) - (b / s)          # 정규화 ExG — 그림자에 강함
    x = cv2.normalize(exg, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    x = cv2.GaussianBlur(x, (5, 5), 0)
    thr, m = cv2.threshold(x, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN,  k, iterations=open_it)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k, iterations=close_it)

    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    if n <= 1:
        return np.zeros_like(m), 0, 0, float(thr)
    i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    big = np.where(lab == i, 255, 0).astype(np.uint8)
    return big, int(st[i, cv2.CC_STAT_AREA]), n - 1, float(thr)


def outline(mask, n_pts=64):
    """대시보드가 그릴 실루엣. <중심 기준> 좌표라 좌표 크기 자체가 면적을 담습니다."""
    c, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not c:
        return None
    c = max(c, key=cv2.contourArea).reshape(-1, 2).astype(np.float32)
    M = cv2.moments(c)
    if M["m00"] == 0:
        return None
    cx, cy = M["m10"] / M["m00"], M["m01"] / M["m00"]
    idx = np.linspace(0, len(c) - 1, n_pts).astype(int)      # 균등 리샘플
    pts = c[idx] - [cx, cy]
    return json.dumps([[round(float(x), 1), round(float(y), 1)] for x, y in pts])


# ══════════════ 본체 ══════════════
def measure(img_path, phase, debug_dir=None, mask_dir=None, C=None):
    C = C or cfg()
    img = cv2.imread(img_path)
    if img is None:
        raise FileNotFoundError(img_path)
    H, W = img.shape[:2]
    stem = os.path.splitext(os.path.basename(img_path))[0]

    ppc = float(C.get("qc", {}).get("px_per_cm_ref", 0) or 0)
    if ppc <= 0:
        print("[WARN] px_per_cm_ref 가 없습니다 — area_cm2 는 null, ok=0 으로 기록됩니다")

    # ── ① 밀림 보정 ──
    rois, drift = C.get("rois", []), None
    if frame_align and os.path.exists(REF_PATH):
        drift = frame_align.align(img_path, REF_PATH, C)
        if drift["ok"] and drift["level"] == "drift":
            rois = frame_align.shift_rois(rois, drift["dx"], drift["dy"], img.shape)
        print(f"[ALIGN] {drift['level']}: {drift['msg']}")

    geom_bad = bool(drift and drift["level"] == "fail")

    out = []
    for roi in rois:
        x, y, w, h = roi["x"], roi["y"], roi["w"], roi["h"]
        if x < 0 or y < 0 or x + w > W or y + h > H:
            print(f'[WARN] {roi["plant_id"]}: ROI 가 프레임 밖 — 건너뜀')
            continue

        crop = img[y:y + h, x:x + w]
        mask, px, blobs, thr = leaf_mask(crop)

        # ── 품질 판정 ──
        edge = bool(mask[0, :].any() or mask[-1, :].any() or
                    mask[:, 0].any() or mask[:, -1].any())
        too_big = px > 0.9 * w * h
        ok = int(px > 0 and not edge and not too_big and ppc > 0 and not geom_bad)
        if edge:
            print(f'[WARN] {roi["plant_id"]}: 잎이 ROI 테두리에 닿음 — 박스를 넓히세요')
        if too_big:
            print(f'[WARN] {roi["plant_id"]}: 마스크가 ROI 의 90%% 초과 — 배경을 잡았을 가능성')

        # ── 배율 검산: 잎이 화분을 덮고 넘치는데 면적이 화분 넓이의 절반도 안 되면
        #    배율이 틀린 것입니다. 면적은 배율의 <제곱>이라 클릭 실수가 크게 증폭됩니다.
        pot_cm = float(C.get("layout", {}).get("pot_cm", 0) or 0)
        if ppc > 0 and pot_cm > 0 and px > 0:
            a_cm2 = px / ppc ** 2
            foot  = 3.14159 * (pot_cm / 2) ** 2
            if a_cm2 < foot * 0.5:
                print(f'[WARN] {roi["plant_id"]}: 면적 {a_cm2:.1f}cm² 가 화분 넓이 {foot:.0f}cm² 의 '
                      f'{a_cm2/foot*100:.0f}% 뿐입니다 — px_per_cm_ref({ppc:.1f}) 를 의심하세요')
            elif a_cm2 > foot * 4:
                print(f'[WARN] {roi["plant_id"]}: 면적 {a_cm2:.1f}cm² 가 화분 넓이의 '
                      f'{a_cm2/foot:.1f}배입니다 — 배율 또는 마스크를 의심하세요')

        row = {"plant_id": roi["plant_id"], "treat": roi.get("treat"),
               "phase": phase, "area_px": px,
               "area_cm2": round(px / ppc ** 2, 2) if ppc > 0 else None,
               "px_per_cm": round(ppc, 3) if ppc > 0 else None,
               "contour": outline(mask), "blobs": blobs, "ok": ok,
               "img_file": os.path.basename(img_path)}
        out.append(row)

        if mask_dir:
            os.makedirs(mask_dir, exist_ok=True)
            cv2.imwrite(f'{mask_dir}/{stem}_{roi["plant_id"]}.png', mask)
        if debug_dir:
            os.makedirs(debug_dir, exist_ok=True)
            vis = crop.copy()
            vis[mask == 0] = (vis[mask == 0] * 0.25).astype(np.uint8)   # 배경 어둡게
            c, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(vis, c, -1, (0, 0, 255), 3)
            cv2.putText(vis, f'{roi["plant_id"]} {row["area_cm2"]}cm2'
                             f'{"" if ok else "  NG"}',
                        (12, 46), cv2.FONT_HERSHEY_SIMPLEX, 1.4,
                        (0, 255, 0) if ok else (0, 0, 255), 3)
            cv2.imwrite(f'{debug_dir}/{stem}_{roi["plant_id"]}.jpg', vis)
    return out


if __name__ == "__main__":
    path  = sys.argv[1] if len(sys.argv) > 1 else REF_PATH
    phase = sys.argv[2] if len(sys.argv) > 2 else "test"
    rows = measure(path, phase, "photos/debug", "photos/mask")
    print(f"\n{'화분':6} {'처리군':8} {'면적px':>10} {'면적cm2':>9} {'조각':>5} {'윤곽':>6} {'판정':>5}")
    for r in rows:
        print(f"  {r['plant_id']:4} {str(r['treat']):8} {r['area_px']:>10,} "
              f"{str(r['area_cm2']):>9} {r['blobs']:>5} "
              f"{'있음' if r['contour'] else '없음':>6} {'ok' if r['ok'] else 'NG':>5}")
    print(f"""
  오버레이를 <반드시 눈으로> 확인하세요. 빨간 윤곽이 잎 경계와 맞지 않으면
  숫자는 의미가 없습니다.  저장 위치: photos/debug/

  보는 법 — 터미널을 하나 더 열어서
      cd ~/plant
      python3 -m http.server 8080
    브라우저에서  http://rasp:8080/photos/debug/   (확인 뒤 Ctrl+C 로 서버 종료)
""")
