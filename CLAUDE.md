# CLAUDE.md — 작업 규칙 · 설계 결정 · 현재 상태

> 상세 작업 이력·세션 서사는 `docs/WORKLOG.md`. 프로젝트 소개·셋업은 `README.md`, 구축 상세는 `docs/manual.html`.

## 운영 구조 (2026-09-12 확정)

- 개발 메인은 **로컬 PC 작업 폴더**. 다른 PC 는 Claude Code 원격제어로 이 세션에 접속(파이에서 직접 편집 금지).
- 배포: 로컬 커밋 → `git push` → 파이 `git pull --ff-only`. 전 과정은 `.\scripts\deploy.ps1` 한 번(푸시 + 파이 pull + `install.sh --update` + 헬스체크).
- 파이(`jh@raspi`, Tailscale `100.80.188.63`, 학교 LAN 192.168.1.209 고정, `~/plant`) 작업트리는 항상 clean 유지.

## sudo 위임 (2026-09-19 등록)

- 파이 `/etc/sudoers.d/plant` 에 다음 명령만 NOPASSWD 등록: `nmcli` · `systemctl` · `apt-get` · `timedatectl` · `install` · `usermod` — install.sh·deploy.ps1·네트워크 등록이 원격으로 도는 데 필요한 최소 집합. 그 외 sudo 작업(reboot 등)은 사람이 실행.
- Wi-Fi 는 NetworkManager 프로필로 관리: `Home803`(집) + `school-cne`(학교 `wi_cne_class_S_2.4G`, 2.4GHz) 자동연결 공존. 새 기기는 같은 방식으로 `nmcli connection add` 등록.
- **환경노드는 파이 USB 직결** (2026-09-28~): 펌웨어 `LINK_MODE=1`, 파이 `plantlink.service`(`hub/serial_bridge.py`)가 시리얼 `PUB <topic> <json>` 을 로컬 MQTT 로 올리고 시각(`T`)·조명(`L`)을 내려준다. Wi-Fi 자격·브로커 IP 불필요, 업로드용 복사본도 저장소 파일 그대로. 재플래싱은 PC 에서 하고 파이에 다시 꽂는다(파이엔 arduino-cli 없음). 급수노드 6대는 여전히 Wi-Fi.
- **학교 Wi-Fi 는 메시 유닛 간 기기 격리** (2026-09-28 실측): 같은 SSID 라도 다른 유닛(BSSID)에 붙은 기기끼리는 ping·TCP 모두 불통, 같은 유닛이면 통함. 노드(Tailscale 없음)가 파이 브로커에 붙으려면 **파이와 같은 유닛**에 있어야 한다. 그래서 파이 `school-cne` 프로필을 실험실에서 가장 센 유닛 `06:29:D5:24:7E:72`(ch11) 에 BSSID 고정 + **정적 IP 192.168.1.209**(gw .1) 로 바꿨다. 펌웨어 BROKER 는 이 IP. 유닛 목록: 7E:42(교무실 PC 쪽)·7E:52·7E:72·7E:82. 파이 위치를 옮기면 `nmcli dev wifi list` 로 가장 센 BSSID 를 다시 고정할 것. PC→파이는 Tailscale(`pl`) 경로라 격리와 무관. 단 학교에서는 Tailscale 이 **DERP 릴레이(hkg, RTT≈200ms, ≈2.7Mbps)** 를 타므로 MJPEG 미리보기는 `preview.jpeg_quality=55 · frame_ms=160`(≈150KB/s) 으로 낮춰 둔다(09-28). 직결 경로가 생기면(같은 메시 유닛·집) 80/80 으로 되돌려도 된다.
- 사용자 업로드용 펌웨어 복사본을 만들 때 **WIFI_SSID·WIFI_PASS·BROKER 세 줄 모두** 실값으로 바꿀 것 — 9/23 에 BROKER 자리표시자(192.168.0.15) 그대로 보내 환경노드가 5일간 리셋 루프에 빠졌다.

## 에이전트 운용 규칙

- **서로 독립적이고 파일 충돌이 없는 작업은 도메인 전문 서브에이전트 팀으로 병렬 수행한다.** 팀 구성은 고정 목록이 아니라 **작업의 도메인에서 그때그때 도출**한다 — 작업을 받으면 ①필요한 전문 관점 2~4개를 먼저 정의하고(예: 이 저장소면 웹 UI·펌웨어·계측/식물생리·문서, 다른 프로젝트면 그 도메인에 맞게) ②관점별 역할 정의를 작성한 뒤 ③병렬 실행한다.
- **역할 정의를 재사용할 가치가 있으면 `.claude/agents/<역할>.md` 파일로 저장**해 팀 구성원을 영속화한다(frontmatter: name·description·tools, 본문: 관점·검토 기준·보고 형식). 일회성 관점은 프롬프트로만 정의해도 된다. 저장된 역할은 다음 작업에서 같은 이름으로 재소집한다.
- 분담 원칙: 같은 파일을 두 에이전트가 만지지 않게 나누고, 브라우저 패널 등 공유 자원은 메인 세션 전용. 검토(읽기)형은 보고서만 받고, 실행(쓰기)형은 대상 파일 집합을 명시해 위임한다.
- 순차 의존 작업·실기기 조작(SSH/배포/플래싱)·사용자와의 핑퐁이 필요한 일은 메인 세션이 직접 한다. 에이전트 결과물은 메인 세션이 검증(테스트·빌드·렌더 확인) 후 커밋한다.

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
- 파이 sudoers 는 명령 화이트리스트라 `sudo -n true` 가 실패한다 — install.sh 는 `sudo -n systemctl --version` 으로 판정(09-28 수정 전엔 매번 "run: …" 만 찍고 유닛을 안 깔았다).
- 파이에는 node 가 없음 → 웹은 PC 빌드 업로드(`deploy.ps1 -Web local`) 또는 GitHub 릴리스 tarball.

## 현재 상태 (2026-09-12)

- `main` 이 유일한 브랜치. 웹 UI 통합 완료, GitHub Pages(개요·매뉴얼·`/app` 데모) 배포 중.
- 파이는 main 최신으로 배포, 서비스 4개 active. 실험 장비(노드·LED)는 미설치 → 화면은 DUMMY DATA 배지 상태(실데이터 유입 시 테이블별 자동 전환).
- 남은 일: ① 카메라 세팅 5단계(http://raspi:8080/camera/setup, 실물 트레이 필요) → 수동 촬영 1회 확인 ② 노드(ESP32) 연결 후 DUMMY 배지 꺼짐 확인 ③ LED: RGBW 61구(핀 9) 설치 완료, 환경노드는 USB 직결 → 새벽 시험 촬영으로 ExG 안정 확인(매뉴얼 패널 19) ④ 선택: 모바일 화분 카드 2열, 라이트 테마 대비 재점검, README 에 데모 스크린샷.
