# Plant Growth Monitoring System — 수분 변동성 생장 실험

> 환경·토양수분을 **MQTT**로 모으고, 카메라가 **투영 캐노피 면적**을 매일 재는 폐루프 급수 시스템. "얼마나 젖었나(평균)"가 아니라 **"수분이 얼마나 흔들렸나(변동성)"**가 생장을 바꾸는지 검정하는 프로젝트.

🔗 **프로젝트개요:** https://xparapx.github.io/Plant_Growth_Monitoring_Demo/
📘 **매뉴얼:** https://xparapx.github.io/Plant_Growth_Monitoring_Demo/manual.html
🖥️ **웹 UI 데모(목 데이터):** https://xparapx.github.io/Plant_Growth_Monitoring_Demo/app/

`Arduino UNO R4 WiFi` · `M5Stack Core S3` · `BME688 · SCD41 · BH1750` · `Watering Unit U101` · `MQTT` · `mosquitto` · `Raspberry Pi 5 · Camera 3` · `OpenCV` · `SQLite` · `FastAPI` · `React · Vite · ECharts`

---

폐루프 급수·온디바이스 센싱·카메라 계측·통계 검정을 한 번에 경험해보고 싶은 누구나 따라 할 수 있는 실험용 데모입니다. **센서 측정 → 폐루프 급수 → 무선 발행(MQTT) → 수집·저장 → 카메라 계측 → 사전등록 분석**의 전 과정을 직접 구성하며, 처리군을 늘리면 대시보드에 칸이 자동으로 추가됩니다.

7노드 전체를 세우기 전에 **3대(환경 1 · 급수 1~2 · 카메라)**로 전 구간을 한 번 관통시키는 예비 데모이며, 여기가 통과하면 나머지는 복제 작업입니다.

---

## 핵심 가설 — 평균은 같게, 흔들림만 다르게

두 처리군은 **평균 토양수분을 똑같이** 맞추고 **변동폭만** 다르게 둡니다.

| 처리군 | 밴드 | 의미 |
|---|---|---|
| **꾸준군 (`stable`)** | 좁게 (raw 밴드 좁게, 예: 1940/1900) | 낮은 변동성 — 평균 근처에서만 오르내림 |
| **널뜀군 (`fluct`)** | 넓게 (raw 밴드 넓게, 예: 2020/1820) | 높은 변동성 — 크게 마르고 크게 채움 |

- 두 처리군의 밴드 **중심 `(RAW_ON+RAW_OFF)/2`는 같게** 맞춥니다 — 폭만 다르게.
- 총 급수량은 **통제하지 않습니다** — 결과로 따라 나오는 값입니다(대시보드 "관수 기록" 카드).
- 수분–생장 곡선이 휘어 있으면(**옌센 부등식**), 평균이 같아도 변동성이 생장의 평균을 바꿉니다: `E[f(수분)] ≠ f(E[수분])`. 곡률 `f″`의 부호가 방향을 정합니다.
- 측정값은 원면적이 아니라 **RGR**(상대생장률, `ln(A)` 의 일수 대비 최소제곱 기울기) — 큰 개체가 절대량으로 더 자라므로 원면적 비교는 부당합니다.
- 결과를 본 뒤 말을 갖다 붙이는 것을 막기 위해, **파종 전 사전등록**으로 가설·분석·효과크기를 미리 못 박습니다.

---

## 시스템 구조

```
환경 노드                급수 노드 (화분별)             허브 (Raspberry Pi)
UNO R4 WiFi          →   M5 Core S3               →   run_collector.py ─→ plant.db ─→ plantsvc (FastAPI :8080)
+ BME688/SCD41/BH1750    + Watering Unit              (planthub.service)   (SQLite)     ├─ 웹 UI (React) — 대시보드·카메라 설정·촬영/LED·시스템
5분 평균 발행            폐루프 급수 + 5분 평균                ↑                        ├─ /api/* · /ws (실시간)
       │                       │                  mosquitto (1883)                    └─ 카메라 미리보기(MJPEG)
       └──── WiFi · MQTT ──────┴──────────────────────┘  ↑
                              Pi Camera → plantsnap.timer(05:50·15:00) → plantsvc capture → plant/tray/growth
```

- **노드 → 브로커**: WiFi 위 MQTT 발행(publish). 브로커는 보고 채널이지 제어 채널이 아닙니다.
- **run_collector.py → 브로커**: 토픽 구독(subscribe) 후 SQLite 에 1행씩 저장 — **plant.db 의 유일한 writer**.
- **plantsvc**: 같은 SQLite 를 읽기 전용으로 표시하고, 카메라·촬영 루틴·설정 파일을 소유합니다. 자체 기록은 `events.db`.
- **급수 노드는 독립적**: 브로커·WiFi가 죽어도 급수는 계속됩니다. 잃는 건 로그뿐.

### MQTT 토픽 / 페이로드

| 토픽 | 보내는 쪽 | 주기 | → 테이블 |
|---|---|---|---|
| `plant/<node>/env` | 환경 노드 | 5분 | `readings` |
| `plant/<node>/soil` | 급수 노드 | 5분 | `soil` (화분별 1행) |
| `plant/<node>/pump` | 급수 노드 | 이벤트 | `pump_log` |
| `plant/tray/growth` | Pi (카메라) | 하루 2회 (dawn 05:50 · pm 15:00) | `growth` (화분별 1행) |

- 시각(`t`)은 **UTC**로 저장하고, 표시·분석 시점에만 `config.json` 의 `tz`(기본 Asia/Seoul)를 적용합니다.

---

## 웹 UI (plantsvc)

Streamlit 대시보드(:8501)와 `setup_camera.py`(:8000)를 **하나의 앱(:8080)** 으로 합쳤습니다. 데스크톱·모바일 반응형, PWA 설치 가능.

| 페이지 | 내용 |
|---|---|
| **개요** `/overview` | 환경 5종 KPI+스파크라인 · 노드 상태 칩 · **Validity**(Δμ 정렬 / σ 비) · 캐노피 실루엣(어제→오늘) · 습윤–건조 톱니 7일 · 최근 관수 · **관수 기록**(처리군별 누적 급수·간격) |
| **처리** `/treatment` | ρ(w) 히스토그램 · (접힌) 해석 참고 곡선 ∩/∪ · 주간 평균 정렬 추세 · 정오 처짐 지수 + 14일 타임라인 |
| **생장** `/growth` | 캐노피 dawn 시계열 · RGR 포레스트 플롯(95 % CI) · Cohen's d · CSV 내보내기 |
| **카메라** `/camera` | 다음 촬영 카운트다운 · 촬영 진행 단계 · 마지막 촬영 결과 · LED 상태(미설치 시 안내) · 지금 촬영 · 이력 |
| **카메라 설정** `/camera/setup` | 실시간 미리보기 위에 ① 노출·초점 ② 배율(두 점 클릭) ③ ROI ④ 처리군 ⑤ 기준 사진 — 예전 `setup_camera.py` 의 5단계 그대로 + ROI 재중심 + 밀림 판정 |
| **시스템** `/system` | 서비스 상태 · 디스크/온도 · DB 행 수 · **config.json 편집** · 로그 · 미발행 측정 재발행 |

**더미 데이터 모드** — 노드·카메라가 아직 없어도 전 화면이 돌아갑니다. 비어 있는 테이블은 합성 데이터로 채우고 그 섹션에 `DUMMY DATA` 배지를 붙입니다(`analysis.dummy_fill: auto`). 실제 메시지가 들어온 테이블부터 실측으로 바뀝니다. 카메라가 없으면 가짜 카메라(`PLANT_FAKE_HW=1`)로 세팅 5단계와 촬영 루틴까지 시험할 수 있고, 가짜 프레임의 측정값은 **절대 발행되지 않습니다**.

**LED 촬영 루틴(자리)** — 촬영은 `LED 점등 → 워밍업 → 촬영 → 소등` 순서로 짜여 있습니다. 하드웨어는 아직 없으므로 기본값은 `led.enabled=false`(noop). 릴레이 모듈을 GPIO(BCM 17)에 달고 `data/config.json` 에서 `led.enabled=true, led.driver="gpiozero"` 로 바꾸면 05:50 점등 → 05:55 촬영이 됩니다.

---

## 폴더 구조

```
hub/plantsvc/   FastAPI 서비스 — settings · schema · config · analytics · vision · camera · led · capture · api · cli · doctor
hub/            run_collector.py(수집기) · run_capture.py 등 레거시 진입점(shim) · config.example.json · plant.conf
web/            React + Vite + TypeScript + Tailwind v4 + ECharts (src/features/* 페이지, src/mock 데모용 목 API)
deploy/systemd/ *.service.tmpl / *.timer.tmpl — 사용자명·경로가 없는 템플릿(설치 시 렌더)
scripts/        install.sh · deploy.ps1 · migrate_legacy.sh · fetch_web.sh · rollback.sh
tests/          pytest (하드웨어 없이 실행)
firmware/       노드 펌웨어 (.ino) + 검증·보정 스케치(diagnostics/)
docs/           프로젝트개요(index.html) · 구축 가이드(manual.html)
data/           런타임 데이터(git 제외): plant.db · events.db · config.json · calib.jpg · photos/
```

### hub

| 파일 | 실행 | 역할 |
|---|---|---|
| `run_collector.py` | systemd `planthub.service` | MQTT 구독 → SQLite 저장 (readings·soil·pump_log·growth) |
| `plantsvc serve` | systemd `plantsvc.service` | 웹 UI + API + 카메라 미리보기 + 촬영 루틴(:8080) |
| `plantsvc capture` | systemd `plantsnap.timer` (05:50·15:00) | LED → 촬영 → 측정 → `growth.jsonl` → MQTT 발행 |
| `plantsvc doctor` | 사람 | venv·카메라·GPIO·DB·브로커·타이머·시간대 점검표 |
| `plantsvc seed` | 사람 · PC | 더미 plant.db 생성(개발·데모) |
| `run_capture.py` / `leaf_measure.py` / `frame_align.py` | 레거시 진입점 | 각각 `plantsvc capture` / `plantsvc.vision.*` 로 연결되는 shim |
| `center_roi.py` · `check_config.py` · `check_db.py` · `reset_run.py` · `backfill.py` · `check_accuracy.py` | 사람 | 보조 도구 — 모두 `PLANT_DATA_DIR` 기준 |
| `config.example.json` | — | 설정 템플릿. 실제 설정은 `data/config.json` (웹 UI 시스템 페이지에서 편집) |
| `plant.conf` | — | mosquitto 브로커 설정 (listener 1883 · anonymous) |

---

## 설치 (Raspberry Pi · 다른 SBC 동일)

```bash
# 1) 클론 — 저장소 구조 그대로 씁니다 (예전처럼 hub/ 를 평탄화하지 않습니다)
git clone https://github.com/xparapx/Plant_Growth_Monitoring_Demo.git ~/plant
cd ~/plant

# 2) (기존 평탄화 설치가 있다면) 데이터만 옮깁니다 — 원본은 지우지 않습니다
scripts/migrate_legacy.sh --from ~/plant.legacy-20260910

# 3) 설치: apt(picamera2·gpiozero·mosquitto) → uv venv(--system-site-packages) → uv sync
#    → data/config.json 시드 → 웹 UI(릴리스 tarball) → systemd 유닛 렌더·설치 → 활성화 → doctor
scripts/install.sh --set-timezone

# 4) 브라우저: http://<pi>:8080  → 카메라 설정 5단계 → 다음 05:50 부터 자동 촬영
```

- 유닛 파일은 `deploy/systemd/*.tmpl` 을 **현재 사용자·현재 경로**로 렌더합니다. `User=`, `WorkingDirectory=`, uv 경로를 손으로 고칠 일이 없습니다.
- 서비스는 `.venv/bin/plantsvc` 를 직접 실행합니다(`uv run` 아님 — 05:50 에 네트워크 해석이 끼어들면 안 됩니다).
- `plantsnap-catchup.service` 가 부팅 때 그날 phase 가 빠졌는지 확인해 워밍업 중 정전으로 놓친 촬영을 복구합니다.
- 개발 PC(Windows)에서: `.\scripts\deploy.ps1` — 브랜치 push → Pi 에서 pull → `install.sh --update` → 헬스 체크.

### PC 에서 개발·시험 (노드·카메라 없이)

```bash
uv sync --group dev
PLANT_FAKE_HW=1 uv run plantsvc serve            # http://localhost:8080  (더미 데이터 + 가짜 카메라)
cd web && npm ci && npm run dev                  # http://localhost:5173  (/api 프록시)
uv run pytest                                    # 31 tests, no hardware
```

> Windows + Smart App Control 환경에서는 최신 pydantic-core DLL 이 차단될 수 있어 `pyproject.toml` 이 win32 에서만 pydantic 2.10 을 고정합니다(Pi 는 최신).

---

## 하드웨어 구성

- **환경 노드**: Arduino **UNO R4 WiFi** + **Grove Base Shield V2** + **BME688**(0x76) + **SCD41**(0x62) + **BH1750**(0x23).
- **급수 노드**: **M5Stack Core S3** + **Watering Unit (U101)** — Port B(G8=수분 / G9=PUMP_EN). 화분 1개당 노드 1개.
- **허브**: **Raspberry Pi 5** — mosquitto · run_collector.py · plantsvc.
- **카메라**: Raspberry Pi **Camera Module 3 — Standard(75°)**.
- **LED(추후)**: 백색 촬영등 + 릴레이/MOSFET 모듈 ← GPIO BCM 17.
- 공통: 노드·허브 모두 **같은 WiFi**(2.4GHz).

> ⚠️ **오토포커스·자동노출·자동화이트밸런스는 반드시 끄세요** — 6주간 고정값(`config.json`)을 유지해야 면적이 왜곡되지 않습니다. 웹 UI 의 [자동 측정 → 고정] 이 한 번 재고 잠급니다.

---

## 펌웨어 업로드 (노드)

1. Arduino IDE 2.x → 보드 패키지: **Arduino UNO R4 Boards** / **M5Stack**
2. 라이브러리: **PubSubClient**, **Sensirion I2C SCD4x**, **Adafruit BME680**, **BH1750**, **M5Unified**
3. `diagnostics/` 로 하드웨어를 검증한 뒤 본 펌웨어 상단 사용자 설정을 수정하고 업로드: `WIFI_SSID / WIFI_PASS / BROKER`, 급수 노드는 `PLANT_ID / TREAT_FLUCT / RAW_DRY·RAW_WET / RAW_ON·RAW_OFF`.
4. 급수 노드의 현재 펌웨어는 `water_node.ino`(폐루프 + 적응 도즈 학습 + MQTT 보고)입니다.

---

## 사용 라이브러리

- **노드**: PubSubClient, Sensirion I2C SCD4x, Adafruit BME680, BH1750, M5Unified
- **허브(Python)**: fastapi, uvicorn, pydantic, paho-mqtt, numpy, pandas, opencv-python-headless, picamera2·gpiozero(apt)
- **웹**: React 18, Vite, TypeScript, Tailwind v4, ECharts, TanStack Query, motion, lucide

---

> 작업 이력은 [docs/WORKLOG.md](docs/WORKLOG.md), 작업 규칙·현재 상태는 [CLAUDE.md](CLAUDE.md) 참고.

*Maintainer: xparapx*
