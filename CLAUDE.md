# CLAUDE.md — 작업 규칙 · 설계 결정 · 현재 상태

> 상세 작업 이력·세션 서사는 `docs/WORKLOG.md`. 프로젝트 소개·셋업은 `README.md`, 구축 상세는 `docs/manual.html`.

## 운영 구조 (2026-09-12 확정)

- 개발 메인은 **로컬 PC 작업 폴더**. 다른 PC 는 Claude Code 원격제어로 이 세션에 접속(파이에서 직접 편집 금지).
- 배포: 로컬 커밋 → `git push` → 파이 `git pull --ff-only`. 전 과정은 `.\scripts\deploy.ps1` 한 번(푸시 + 파이 pull + `install.sh --update` + 헬스체크).
- 파이(`jh@raspi`, Tailscale `100.80.188.63`, `~/plant`) 작업트리는 항상 clean 유지.

## sudo 위임 (2026-09-19 등록)

- 파이 `/etc/sudoers.d/plant` 에 다음 명령만 NOPASSWD 등록: `nmcli` · `systemctl` · `apt-get` · `timedatectl` · `install` · `usermod` — install.sh·deploy.ps1·네트워크 등록이 원격으로 도는 데 필요한 최소 집합. 그 외 sudo 작업(reboot 등)은 사람이 실행.
- Wi-Fi 는 NetworkManager 프로필로 관리: `Home803`(집) + `school-cne`(학교 `wi_cne_class_S_2.4G`, 2.4GHz) 자동연결 공존. 새 기기는 같은 방식으로 `nmcli connection add` 등록.

## 검증 방법 (PC)

```bash
uv run pytest -q                 # 백엔드 테스트
cd web && npm run lint && npm run build
```

- 브라우저 확인: `.claude/launch.json` 의 `api`(PLANT_FAKE_HW=1, :8080)와 `web`(:5173) → http://localhost:5173
- 백엔드 없이: `http://localhost:5173/?mock=1` (`&scenario=full|env-only|none|conflict|unknown-treat|one-group|setup-fresh|setup-done|capture-failed`)

## SSH 별명 (교무실 PC `~/.ssh/config`, 2026-09-19)

- `pl` = 식물 파이(jh@raspi) · `aq` = 공기질(arduino@aqhub) · `tr` = 교통위험 Jetson(kjhs@orin) · `mb` = 급식실 파이(xparapx@rsp)
- `mb-cf` = 급식실 파이 예비 경로(Cloudflare 터널) — 급식실 네트워크가 Tailscale 컨트롤 서버를 차단해 `mb` 는 현재 불통. 네트워크 이전 후 `sudo tailscale up` 재인증 필요.
- HostName 은 Tailscale 기기명이라 어느 네트워크에서든 동일. 학교 유선망(10.23.x)에 기기를 직접 붙이지 말 것(차단·MAC 등록제).

## 알아둘 것 (환경 제약)

- Windows Smart App Control 이 최신 pydantic-core DLL 을 막아 win32 에서만 `pydantic<2.11` 고정(pyproject). 파이는 최신.
- PowerShell 5.1: `&&` 없음. 원격 파이썬 원라이너 따옴표가 깨지니 스크립트 파일을 scp 해서 실행한다.
- 앱 내장 브라우저는 LAN 주소를 막는다 → 파이 화면 확인은 `ssh -N -L 8081:127.0.0.1:8080 raspi` 후 http://localhost:8081
- 파이에는 node 가 없음 → 웹은 PC 빌드 업로드(`deploy.ps1 -Web local`) 또는 GitHub 릴리스 tarball.

## 현재 상태 (2026-09-12)

- `main` 이 유일한 브랜치. 웹 UI 통합 완료, GitHub Pages(개요·매뉴얼·`/app` 데모) 배포 중.
- 파이는 main 최신으로 배포, 서비스 4개 active. 실험 장비(노드·LED)는 미설치 → 화면은 DUMMY DATA 배지 상태(실데이터 유입 시 테이블별 자동 전환).
- 남은 일: ① 카메라 세팅 5단계(http://raspi:8080/camera/setup, 실물 트레이 필요) → 수동 촬영 1회 확인 ② 노드(ESP32) 연결 후 DUMMY 배지 꺼짐 확인 ③ LED: Grove RGB 스틱(5구)×2 를 환경노드 D4·D5 에 설치 → `USE_LIGHT=1` 펌웨어 업로드 → 새벽 시험 촬영으로 ExG 안정 확인(매뉴얼 패널 19) ④ 선택: 모바일 화분 카드 2열, 라이트 테마 대비 재점검, README 에 데모 스크린샷.
