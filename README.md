# Plant Growth Monitoring System — 수분 변동성 생장 실험

> 환경·토양수분을 **MQTT**로 모으고, 카메라가 **투영 캐노피 면적**을 매일 재는 폐루프 급수 시스템. "얼마나 젖었나(평균)"가 아니라 **"수분이 얼마나 흔들렸나(변동성)"**가 생장을 바꾸는지 검정하는 프로젝트.

🔗 **프로젝트개요:** https://xparapx.github.io/Plant_Growth_Monitoring_Demo/  
📘 **매뉴얼:** https://xparapx.github.io/Plant_Growth_Monitoring_Demo/manual.html

`Arduino UNO R4 WiFi` · `M5Stack Core S3` · `BME688 · SCD41 · BH1750` · `Watering Unit U101` · `MQTT` · `mosquitto` · `Raspberry Pi 5 · Camera 3` · `OpenCV` · `SQLite` · `Streamlit`

---

폐루프 급수·온디바이스 센싱·카메라 계측·통계 검정을 한 번에 경험해보고 싶은 누구나 따라 할 수 있는 실험용 데모입니다. **센서 측정 → 폐루프 급수 → 무선 발행(MQTT) → 수집·저장 → 카메라 계측 → 사전등록 분석**의 전 과정을 직접 구성하며, 처리군을 늘리면 대시보드에 칸이 자동으로 추가됩니다.

7노드 전체를 세우기 전에 **3대(환경 1 · 급수 1~2 · 카메라)**로 전 구간을 한 번 관통시키는 예비 데모이며, 여기가 통과하면 나머지는 복제 작업입니다.

---

## 핵심 가설 — 평균은 같게, 흔들림만 다르게

두 처리군은 **평균 토양수분을 똑같이** 맞추고 **변동폭만** 다르게 둡니다.

| 처리군 | 밴드 | 의미 |
|---|---|---|
| **꾸준군 (A)** | 좁게 (예: 33 / 36%) | 낮은 변동성 — 평균 근처에서만 오르내림 |
| **널뜀군 (B)** | 넓게 (시드는 지점 / 포장용수량) | 높은 변동성 — 크게 마르고 크게 채움 |

- 총 급수량은 **통제하지 않습니다** — 결과로 따라 나오는 값입니다.
- 수분–생장 곡선이 휘어 있으면(**옌센 부등식**), 평균이 같아도 변동성이 생장의 평균을 바꿉니다: `E[f(수분)] ≠ f(E[수분])`. 곡률 `f″`의 부호가 방향을 정합니다.
- 측정값은 원면적이 아니라 **RGR**(상대생장률, `(ln A₂ − ln A₁)/Δt`) — 큰 개체가 절대량으로 더 자라므로 원면적 비교는 부당합니다.
- 결과를 본 뒤 말을 갖다 붙이는 것을 막기 위해, **파종 전 사전등록**으로 가설·분석·효과크기를 미리 못 박습니다.

---

## 프로젝트 개요

- **프로젝트개요**(`docs/index.html`) — 요약·흐름도·핵심가설·준비물·기술스택을 한눈에.
- **매뉴얼**(`docs/manual.html`) — 준비물·전체 구조·단계별 구축 가이드(브로커·hub.py·펌웨어·급수 보정·카메라 계측·대시보드·분석·트러블슈팅). 모든 코드가 본문에 포함되어 복사 버튼으로 바로 쓸 수 있습니다.

| 단계 | 내용 | 도구 |
|---|---|---|
| ① 측정 | 환경(온습도·VPD·CO₂·조도) + 화분별 토양수분 | BME688 · SCD41 · BH1750 · 수분센서 |
| ② 급수 | 밴드 안에서 dose·soak·verify 폐루프 | Core S3 + Watering Unit |
| ③ 발행 | NTP 정각정렬, 5분 평균 1건 MQTT 발행 | WiFi · MQTT |
| ④ 수집 | 메시지를 받아 DB에 저장 | hub.py · SQLite |
| ⑤ 계측 | 위에서 찍은 사진 → 투영 캐노피 면적 | Pi Camera · OpenCV (ExG+Otsu) |
| ⑥ 분석 | RGR·효과크기·사전등록 검정 | Streamlit · pandas |

---

## 시스템 구조

```
환경 노드                급수 노드 (화분별)          허브 (PC → Pi)
UNO R4 WiFi          →   M5 Core S3            →   hub.py ─→ SQLite ─→ dashboard.py
+ BME688/SCD41/BH1750    + Watering Unit           (수집·저장)        (웹 :8501)
5분 평균 발행            폐루프 급수 + 5분 평균          ↑
       │                       │                mosquitto (1883)
       └──── WiFi · MQTT ──────┴──────────────────┘  ↑
                                              Pi Camera → leafcv.py → plant/tray/growth
```

- **노드 → 브로커**: WiFi 위 MQTT 발행(publish)
- **hub.py → 브로커**: 토픽 구독(subscribe) 후 SQLite에 1행씩 저장
- **dashboard.py**: 같은 SQLite를 읽기 전용으로 표시 (수집과 표시 분리)
- **급수 노드는 독립적**: 브로커·WiFi가 죽어도 급수는 계속됩니다. 잃는 건 로그뿐.
- 허브·브로커·대시보드는 **플랫폼 무관** — Pi 도착 전까지 전부 PC에서 돌리고, Pi에는 카메라만 추가하면 됩니다.

### MQTT 토픽 / 페이로드

| 토픽 | 보내는 쪽 | 주기 | → 테이블 |
|---|---|---|---|
| `plant/<node>/env` | 환경 노드 | 5분 | `readings` |
| `plant/<node>/soil` | 급수 노드 | 5분 | `soil` (화분별 1행) |
| `plant/<node>/pump` | 급수 노드 | 이벤트 | `pump_log` |
| `plant/tray/growth` | Pi (카메라) | 1일 | `growth` (화분별 1행) |

- 구독: `plant/+/env`, `plant/+/soil`, `plant/+/pump`, `plant/+/growth` (`+` = 모든 노드)
- 시각(`t`)은 **UTC**로 저장하고, 표시·분석 시점에만 +9h(KST)를 적용합니다.
- 노드 ID는 MAC 끝 3바이트로 자동 생성(`wtr_XXXXXX`)되어 충돌하지 않습니다.

---

## 하드웨어 구성

- **환경 노드**: Arduino **UNO R4 WiFi**(WiFi 필수, Minima 불가) + **Grove Base Shield V2**(I2C 4포트 → 허브 불필요) + **BME688**(0x76, 온습도·기압·VPD) + **SCD41**(0x62, CO₂ 전용) + **BH1750/DLight**(0x23, 조도) — 같은 I2C 버스 공유. (MLX90640 열화상은 2단계)
- **급수 노드**: **M5Stack Core S3** + **Watering Unit (U101)** — Port B(G8=수분 Analog / G9=PUMP_EN, 실측 확정). 화분 1개당 노드 1개. 내장 배터리가 펌프 인러시 전류를 완충.
- **허브**: 처음엔 **PC(Windows)**, 이후 **Raspberry Pi 5**(카메라 전용) — mosquitto·hub.py·대시보드 구동.
- **카메라**: Raspberry Pi **Camera Module 3 — Standard(75°)** (⚠️ Wide·NoIR 아님).
- 공통: 노드·허브 모두 **같은 WiFi**(2.4GHz).

> ⚠️ **전압 스위치** — UNO R4 WiFi는 Grove Base Shield를 반드시 **5V**로. 잘못 두면 센서·보드가 손상될 수 있습니다.
> ⚠️ **오토포커스·자동노출·자동화이트밸런스는 반드시 끄세요** — 6주간 고정값(`config.json`)을 유지해야 면적이 왜곡되지 않습니다.

---

## 폴더 구조

```
firmware/    노드 펌웨어 (.ino) + 검증·보정 스케치(diagnostics/)
hub/         허브 파이썬 (수집·대시보드·비전·브로커 설정)
docs/        프로젝트개요(index.html) · 구축 가이드(manual.html)
```

### firmware

| 파일 | 기종 | 역할 |
|---|---|---|
| `plant_env_r4wifi.ino` | UNO R4 WiFi | 환경 5종 측정 → `plant/<node>/env` 발행 |
| `plant_water_cores3.ino` | M5 Core S3 | 폐루프 급수 + 토양수분 → `soil`·`pump` 발행 |
| `diagnostics/i2c_scan.ino` | UNO R4 | I2C 주소 스캔 (무엇이 붙어 있나) |
| `diagnostics/env_sensor_test.ino` | UNO R4 | 센서값 확인 (통신 전 하드웨어 검증) |
| `diagnostics/pin_id.ino` | Core S3 | 어느 핀이 아날로그인가 |
| `diagnostics/water_touch_test.ino` | Core S3 | 터치로 펌프 + 수분 반응 확인 |
| `diagnostics/pump_burst.ino` | Core S3 | 3초 강제 구동 → 급수량 mL 측정 |
| `diagnostics/calib_sat.ino` | Core S3 | 포화점 자동 탐지 (화분당 30분) |

### hub

| 파일 | 역할 |
|---|---|
| `hub.py` | MQTT 구독 → SQLite 저장 (readings·soil·pump_log·growth 4테이블) |
| `dashboard.py` | SQLite 읽어 환경·급수·생장 표시 (Streamlit) |
| `snap.py` | 보정용 정지 1장 촬영 (초점·노출·WB 고정) |
| `make_marker.py` | ArUco 마커(자·스케일) 인쇄용 이미지 생성 |
| `leafcv.py` | ExG + Otsu → 투영 캐노피 면적(cm²) 환산 |
| `validate.py` | 면적을 아는 종이 잎으로 정확도 검증 (PASS/FAIL) |
| `config.json` | ROI·스케일·캡처 고정값 (마커 mm·렌즈·노출) |
| `plant.conf` | mosquitto 브로커 설정 (listener 1883 · anonymous) |

---

## 허브 셋업 (PC → Pi 공통)

```bash
# 1) 파이썬 환경 (uv)
mkdir plant && cd plant
uv init --no-readme && rm -f main.py
uv add paho-mqtt pandas plotly streamlit streamlit-autorefresh numpy opencv-python-headless

# 2) 로컬 브로커 (mosquitto)
#    Windows: mosquitto.exe -c plant.conf -v
#    Pi     : sudo cp plant.conf /etc/mosquitto/conf.d/ && sudo systemctl restart mosquitto

# 3) 수집 + 대시보드 실행
uv run python hub.py                          # MQTT 구독 → SQLite
uv run streamlit run dashboard.py --server.address 0.0.0.0 --server.port 8501
```

대시보드: `http://<허브 IP>:8501`

> ⚠️ `python dashboard.py`로는 실행되지 않습니다. 반드시 `streamlit run`(또는 `uv run streamlit run`)을 사용하세요.
> **노드 없이 먼저 검증** — `mosquitto_pub`으로 가짜 env/soil/pump 메시지를 쏘아 hub.py가 4테이블에 잘 넣는지 확인한 뒤 노드를 만드세요. 이러면 나중에 노드가 안 될 때 hub.py는 용의선상에서 빠집니다.

---

## 펌웨어 업로드 (노드)

1. Arduino IDE 2.x → 보드 패키지: **Arduino UNO R4 Boards** / **M5Stack**
2. 라이브러리: **PubSubClient**, **Sensirion I2C SCD4x**(신버전), **Adafruit BME680**(BME688 호환), **BH1750**, **M5Unified**
3. 먼저 `diagnostics/`로 하드웨어를 검증(통신 전에 센서·펌프가 되는지)한 뒤, 본 펌웨어 상단 사용자 설정을 수정하고 업로드:
   - `WIFI_SSID` / `WIFI_PASS` — 현장 WiFi
   - `BROKER` — PC의 IPv4(`ipconfig`), Pi 도착 후 Pi IP로 교체
   - 급수 노드: `PLANT_ID`(화분 번호) / `TREAT`(A=꾸준군, B=널뜀군)
   - `SOIL_DRY`·`SOIL_WET`·`DOSE_MS` — **보정 결과로 반드시 교체** (그대로 쓰지 말 것)
   - `ON_BELOW`·`OFF_AT` — 처리 밴드. **이 두 줄이 곧 실험의 처리 조건**입니다.

> `WiFiS3`(R4) / `WiFi`(Core S3)는 보드 패키지에 내장되어 별도 설치가 필요 없습니다.

---

## 노드 추가 / 처리군 확장

- 노드는 MAC 끝 3바이트로 ID를 자동 생성하므로, **펌웨어를 그대로 올리기만 하면** 대시보드에 칸이 자동 추가됩니다.
- 데모의 노드 2대를 그대로 쓰고 급수 노드를 복제해 7노드로 확장 — `PLANT_ID`와 `TREAT`만 바꿔 업로드하며, **hub.py는 수정할 필요가 없습니다.**

---

## 사용 라이브러리

- **노드**: PubSubClient, Sensirion I2C SCD4x, Adafruit BME680, BH1750, M5Unified, WiFiS3/WiFi(내장)
- **허브**: paho-mqtt, pandas, plotly, numpy, opencv, streamlit, streamlit-autorefresh, picamera2(Pi) (uv 프로젝트로 관리)

---

## 작업 로그

- **2026-07**: 3대 예비 데모 초기 공개 — 환경 노드(UNO R4 WiFi) · 급수 노드(M5 Core S3) · Pi 카메라 관통 구축
- **2026-07**: 폐루프 급수 상태기계 — dose·soak·verify·일일상한·fail-safe OFF, 브로커 단절 내성 확보
- **2026-07**: 카메라 계측 파이프라인 — ExG+Otsu 투영 캐노피 면적, ArUco 스케일, 종이잎 검증(`validate.py`)
- **2026-07**: 수분 변동성 실험 설계 — 꾸준군/널뜀군 밴드, RGR·효과크기·사전등록 프로토콜 확정
- **2026-07**: 허브 플랫폼 무관화 — mosquitto·hub.py·dashboard.py를 PC에서 완성, Pi는 카메라만 추가

---

*Maintainer: xparapx*
