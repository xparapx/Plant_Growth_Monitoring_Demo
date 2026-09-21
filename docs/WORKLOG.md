# 작업 이력 (WORKLOG)

> 최신이 위. 의미 있는 변경마다 갱신(커밋마다는 아님). 작업 규칙·현재 상태는 저장소 루트 `CLAUDE.md`, 프로젝트 소개는 `README.md`.

## 2026-09

- **09-22 프로젝트 지도 생성** — `docs/project-map.html`(+`project-map.json`, 29노드·35간선·DB 2) — 설계 맵 5레인·스크립트 연결 지도·plant.db/events.db 스키마·핵심 기술 탭. project-map 스킬 §3c design-craft 품질 필터 첫 적용: SVG 노드 `:focus-visible` 링을 템플릿에 추가(수정 1건), 나머지 통과. 갱신은 json 을 고쳐 `render.py` 재실행.
- **09-19 급수노드(water_node) 현장 운용 개선** — ① 처리군을 컴파일 스위치에서 **터치 선택 칩([STBL][FLCT], NVS 저장)** 으로 — 같은 펌웨어를 전 노드에 올리고 현장 지정(노드별 수정은 `NODE_ID`/`PLANT_ID` 두 줄뿐, wN↔pN 동번호 매핑). ② 급수 트리거 확인(10초×연속 3회 RAW_ON 초과) — 좁은 stable 밴드(40카운트)에서 센서 요동 오급수 차단. ③ SAFE 화면 초기 젖음 게이지(1750~1800: POUR/DRAINING/OK→AUTO) — 전 화분 동일 출발선 절차를 화면이 안내. ④ 수동 펌프(PUMP) 세션을 `reason=prime` 이벤트로 DB 기록. ⑤ UI 3버튼(AUTO/PUMP/RESET 1.5초 홀드) + 탭 판정 wasClicked 통일(STOP 미동작 대응). 파이는 학교 공유기(192.168.1.214, school-cne)로 이전 완료, 환경노드 조명(4구×2, 핀8·9) 실물 점등 테스트 완료.
- **09-19 조명 체계 정리** — ① 카메라 설정 UI: 보기 전용 90° 회전(브라우저 표시만, 사진·좌표 원본 유지), 조명 켬/끔 버튼(→ MQTT `plant/light/set`, 노드 30분 자동 소등), 카메라 수동 켜기/끄기 버튼. ② 환경노드 정식 펌웨어: RGB 4구×2(핀 8·9), 시간 창 + MQTT 원격 점등 + 시리얼 테스트. ③ hub 의 옛 GPIO LED 훅(config `led` 절·LedController·`plantsvc led` CLI·촬영 루틴 점등 단계·systemd led off·웹 LED 카드) 전면 제거 — 조명 코드는 노드 펌웨어에만 존재. 학교망 이슈: Tailscale 컨트롤·GitHub SSH 차단 확인 → 파이 remote HTTPS 전환, 급식실 파이는 `mb-cf`(Cloudflare) 경로 사용.

- **09-19 카메라 90° 회전** — 설치 방향 보정용 `capture.rotation`(0/90/180/270) 신설. picamera2 Transform 은 90도가 안 되므로 서버에서 프레임 회전(미리보기 grab·정지촬영 후처리 모두), ROI·격자·프레임폭 계산은 `eff_size` 기준으로 통일. 설정 UI 미리보기에 ⟳ 90° 회전 버튼(+세로 화면 동적 종횡비), 회전 시 배율·ROI·calib 재설정 경고. mock 동등 반영.
- **09-18 환경노드 개정** — `plant_env_r4wifi.ino`: 블로킹 재접속(최대 85초 루프 정지) 제거 → water_node 식 논블로킹 `netReady()`(10초 간격 1회 시도), 발행 실패 유실 → 오프라인 큐 8건(payload 에 버킷 시각 포함이라 늦게 발행돼도 시각 정확), String → 정적 버퍼, WDT 5초, NTP 하루 1회 재동기화, 네오픽셀 시간 점등 구현(`USE_LIGHT=1` — Grove RGB 스틱 5구×2, D4·D5, 밝기 80/255 고정, KST 05:45~06:15, 창 밖·NTP 실패 시 무조건 소등).
- **09-18 급수 펄스 분할** — dry_probe 주기 측정 경험을 반영해 `water_node.ino` 도즈를 **0.2초 펄스 + 2.5초 스며듦·측정** 열로 분할(새 상태 `S_GAP`). 간격 측정에서 목표(RAW_OFF) 도달 시 남은 예산을 버리고 조기 중지 — 드로퍼 물튐·과급수 방지. 학습(kPerMs)·3분 침투 검증·no-rise/MAX_SHOTS 고장 판정은 그대로(2.5초 측정은 조기 중지용 참고). `dry_probe.ino`를 `firmware/tools/`에 수록.
- **09-18 LED 방식 변경** — 파이 GPIO + 릴레이/MOSFET 계획을 폐기하고 **환경노드(R4 WiFi) 네오픽셀 스트립의 시간 기반 독립 점등**(NTP, 05:45 점등/06:15 소등, 촬영 05:50 유지)으로 확정. 스위칭 소자·MQTT 명령 불요, 파이는 hub 역할만. 스트립 종류(RGBW 권장)·펌웨어 로직은 추후. 매뉴얼 패널 19·README·CLAUDE.md 반영. hub `led.*` 훅은 noop 그대로 존치.
- **09-12 운영 구조 확정·문서 재편** — ssh 원격 편집 시도를 롤백하고 "로컬 PC 개발 → push → 파이 pull(--ff-only)" 구조 확정(`scripts/deploy.ps1` 한 번으로 배포). README 작업 로그·dev-notes 를 WORKLOG/CLAUDE.md 로 재편.
- **09-12 main 머지 완료** — `feat/web-ui` 전체가 main 에 머지(376df62). GitHub Pages(Actions 소스)로 개요·매뉴얼·웹 데모(`/app`) 배포 확인. 파이도 main 최신으로 배포, 서비스 4개(mosquitto · planthub · plantsvc · plantsnap.timer) 모두 active.
- **09-11 디자인 반영** — Claude Design 목업(턴 3, plantlab 네이비 팔레트)을 웹 UI 에 반영: 네이비 다크 기본 테마, Space Grotesk, `plantlab°` 워드마크, 니들 게이지 5종, Overview 우측 Treatment check/급수 이벤트, KPI·수분 궤적·밴드 설정·분포, 화분 카드 3×2·RGR 추이·ΔRGR, 카메라 세팅 프리뷰+5단계 레일. 원본은 `design/Plant Monitor Mockups.turn3.dc.html`, 매핑표는 `design/README.md`. Overview 하단에 관수 기록(`WaterCard`)·촬영 일지(`CaptureLogCard`) 추가. xl 12열 그리드에서 카드가 1열로 눌리던 문제 수정.
- **09 웹 UI 통합** — Streamlit(:8501)·setup_camera.py(:8000)를 FastAPI + React 단일 앱(:8080)으로 대체. LED 촬영 루틴 자리, 더미 데이터 모드(`analysis.dummy_fill=auto`), 클론 그대로 설치되는 `install.sh` 와 사용자 무관 systemd 템플릿, GitHub Actions(CI·릴리스·Pages 데모). systemd 시각 문자열 ISO 변환, CLI seed 인자 호환 수정.

## 2026-08

- 급수 노드 MQTT 보고·적응 도즈 학습, 미리보기·촬영 화각 통일(lores), center_roi.

## 2026-07

- **07-26 매뉴얼 대규모 개정** — `setup_`/`check_`/`run_` 체계, frame_align 밀림 보정, systemd 무인 운용.
- 3대 예비 데모 초기 공개 — 환경 노드 · 급수 노드 · Pi 카메라 관통 구축. 폐루프 급수 상태기계 · 카메라 계측 파이프라인(ExG+Otsu) · 수분 변동성 실험 설계 · 허브 플랫폼 무관화.
