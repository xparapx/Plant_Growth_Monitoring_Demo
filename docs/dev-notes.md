# 개발 인수인계 노트

> 다른 PC(학교)에서 이어서 작업할 때 먼저 읽는 파일. 대화 컨텍스트가 없어도 여기만 보고 이어갈 수 있게 유지한다.
> 마지막 갱신: 2026-09-12 (main 머지 완료, 운영 구조 확정)

## 운영 구조 (확정)

- 개발 메인은 **로컬 PC 작업 폴더**. 다른 PC 에서는 Claude Code 원격제어로 이 PC 세션에 접속해 작업한다(파이에서 직접 편집 금지).
- 배포: 로컬 커밋 → `git push` → 파이가 `git pull --ff-only` — 전 과정은 `scripts/deploy.ps1` 한 번으로 수행(푸시 + 파이 pull + install + 헬스체크).
- 파이 작업트리는 항상 clean 유지. Mealboard 프로젝트도 같은 구조.

## 지금 상태

- `feat/web-ui` 는 **main 에 머지 완료**(376df62), 로컬 브랜치 삭제됨. GitHub Pages 도 Actions 소스로 배포 중(`/`, `/app` 모두 200).
- 파이(`jh@raspi`, Tailscale `100.80.188.63`, `~/plant`)는 `main` 최신 커밋으로 배포돼 있고 서비스 4개(mosquitto · planthub · plantsvc · plantsnap.timer) 모두 active.
  UI: http://raspi:8080 (같은 Tailscale 계정 기기 어디서나).
- 실험 장비(노드·LED)는 아직 없음 → 화면은 전부 **DUMMY DATA** 배지 상태. 실제 MQTT 행이 들어오는 테이블부터 자동으로 실데이터로 바뀐다(`analysis.dummy_fill=auto`).
- 파이 카메라(imx708)는 실물이 붙어 있음. **카메라 세팅 5단계**(http://raspi:8080/camera/setup)는 아직 안 했음 → ROI/px_per_cm 이 없어 촬영이 ok=0 으로 끝난다. 이건 실물 트레이를 보며 직접 해야 하는 일.
- LED 는 미설치(noop). 설치 후 `data/config.json` 에서 `led.enabled=true, led.driver="gpiozero"`.

## 디자인 반영 (2026-09-11)

- Claude Design 목업(턴 3, 브랜드 팔레트) 원본을 `design/Plant Monitor Mockups.turn3.dc.html` 로 저장했고, `design/README.md` 에 목업 → 토큰/컴포넌트 매핑표가 있다.
- 적용 요약: 네이비 다크 테마가 기본(`html[data-theme=dark]`), Space Grotesk, `plantlab°` 워드마크, 대문자 내비, 니들 게이지 5종, 3a 우측 Treatment check/급수 이벤트, 3b KPI·수분 궤적·밴드 설정·분포, 3c 화분 카드 3×2·RGR 추이·ΔRGR, 3d 프리뷰+5단계 레일+저장 버튼.
- "3a 허전함" 보강: 관수 기록(`WaterCard`) + 촬영 일지(`CaptureLogCard`) 카드를 Overview 하단에 추가.
- 라이트 테마는 같은 색 관계를 #F2F2F2 위에 옮긴 대안. 헤더 우측 토글.

## 검증 방법 (PC)

```bash
uv run pytest -q                 # 백엔드 32개
cd web && npm run lint && npm run build
```

브라우저 확인: `.claude/launch.json` 의 `api`(PLANT_FAKE_HW=1, :8080) 와 `web`(:5173) 를 띄우고 http://localhost:5173 .
백엔드 없이 보려면 `http://localhost:5173/?mock=1` (시나리오: `&scenario=full|env-only|none|conflict|unknown-treat|one-group|setup-fresh|setup-done|capture-failed`).

## 파이 배포 절차 (PC 에서, 비밀번호 불필요 — 공개키 + sudo NOPASSWD)

1. `cd web && npm run build && tar -czf web-dist.tar.gz -C . dist` → `scp web/web-dist.tar.gz raspi:~/plant/web/`
2. `ssh raspi 'cd ~/plant && git pull --ff-only && rm -rf web/dist && tar -xzf web/web-dist.tar.gz -C web && pkill -f "plantsvc serve"'`
   (plantsvc 는 `Restart=always` 라 자동 재기동. 파이에는 node 가 없어 PC 빌드를 올린다.)
3. 파이썬 의존성이 바뀌었으면 `ssh raspi 'cd ~/plant && bash scripts/install.sh --update --web=skip'`.
4. 확인: `ssh raspi 'systemctl is-active plantsvc planthub mosquitto plantsnap.timer; curl -s localhost:8080/api/system/status | head -c 300'`

## 남은 일 (우선순위)

1. 파이에서 카메라 세팅 5단계 → calib.jpg 생성 → `sudo systemctl start plantsnap.service` 로 수동 촬영 1회 확인(journal 에 `LED skipped` → `shot` → `published`).
3. 노드(ESP32) 연결 후 DUMMY 배지가 테이블별로 꺼지는지 확인.
4. LED 하드웨어 설치 시 §9-5(계획 파일) 절차.
5. 선택: 모바일 화분 카드 2열, 라이트 테마 대비 재점검, GitHub Pages 데모 스크린샷을 README 에.

## 알아둘 것

- Windows Smart App Control 이 최신 pydantic-core DLL 을 막아 win32 에서만 `pydantic<2.11` 고정(pyproject).
- PowerShell 5.1: `&&` 없음. 원격 파이썬 원라이너 따옴표가 깨지니 스크립트 파일을 scp 해서 실행한다.
- 앱 내장 브라우저는 LAN 주소를 막는다 → 파이 화면 확인은 `ssh -N -L 8081:127.0.0.1:8080 raspi` 후 http://localhost:8081 .
