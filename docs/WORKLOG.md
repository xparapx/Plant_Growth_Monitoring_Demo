# 작업 이력 (WORKLOG)

> 최신이 위. 의미 있는 변경마다 갱신(커밋마다는 아님). 작업 규칙·현재 상태는 저장소 루트 `CLAUDE.md`, 프로젝트 소개는 `README.md`.

## 2026-09

- **09-12 운영 구조 확정·문서 재편** — ssh 원격 편집 시도를 롤백하고 "로컬 PC 개발 → push → 파이 pull(--ff-only)" 구조 확정(`scripts/deploy.ps1` 한 번으로 배포). README 작업 로그·dev-notes 를 WORKLOG/CLAUDE.md 로 재편.
- **09-12 main 머지 완료** — `feat/web-ui` 전체가 main 에 머지(376df62). GitHub Pages(Actions 소스)로 개요·매뉴얼·웹 데모(`/app`) 배포 확인. 파이도 main 최신으로 배포, 서비스 4개(mosquitto · planthub · plantsvc · plantsnap.timer) 모두 active.
- **09-11 디자인 반영** — Claude Design 목업(턴 3, plantlab 네이비 팔레트)을 웹 UI 에 반영: 네이비 다크 기본 테마, Space Grotesk, `plantlab°` 워드마크, 니들 게이지 5종, Overview 우측 Treatment check/급수 이벤트, KPI·수분 궤적·밴드 설정·분포, 화분 카드 3×2·RGR 추이·ΔRGR, 카메라 세팅 프리뷰+5단계 레일. 원본은 `design/Plant Monitor Mockups.turn3.dc.html`, 매핑표는 `design/README.md`. Overview 하단에 관수 기록(`WaterCard`)·촬영 일지(`CaptureLogCard`) 추가. xl 12열 그리드에서 카드가 1열로 눌리던 문제 수정.
- **09 웹 UI 통합** — Streamlit(:8501)·setup_camera.py(:8000)를 FastAPI + React 단일 앱(:8080)으로 대체. LED 촬영 루틴 자리, 더미 데이터 모드(`analysis.dummy_fill=auto`), 클론 그대로 설치되는 `install.sh` 와 사용자 무관 systemd 템플릿, GitHub Actions(CI·릴리스·Pages 데모). systemd 시각 문자열 ISO 변환, CLI seed 인자 호환 수정.

## 2026-08

- 급수 노드 MQTT 보고·적응 도즈 학습, 미리보기·촬영 화각 통일(lores), center_roi.

## 2026-07

- **07-26 매뉴얼 대규모 개정** — `setup_`/`check_`/`run_` 체계, frame_align 밀림 보정, systemd 무인 운용.
- 3대 예비 데모 초기 공개 — 환경 노드 · 급수 노드 · Pi 카메라 관통 구축. 폐루프 급수 상태기계 · 카메라 계측 파이프라인(ExG+Otsu) · 수분 변동성 실험 설계 · 허브 플랫폼 무관화.
