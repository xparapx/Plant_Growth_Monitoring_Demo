# design/ — Claude Design 목업 작업본

원본: Claude Design 프로젝트 **Plant Monitor Mockups**
(`https://claude.ai/design/p/5e929b1b-ca2a-4b99-bcbe-78284c2346f1?file=Plant+Monitor+Mockups.dc.html`).
프로젝트에는 `Plant Monitor Mockups.dc.html`(126 KB, 턴 1–3), `support.js`(Claude Design 의 dc-runtime, 디자인 정보 없음), `github.md` 가 있다.

| 파일 | 내용 |
|---|---|
| `Plant Monitor Mockups.turn3.dc.html` | 최종 방향 **턴 3** — 브랜드 팔레트(#173046 · #2C5979 · #D84C27 · #F2F2F2 · #C0C0C0) + 환경변수 Plotly 기본색, 페이지 목업 4종(3a Overview · 3b Treatment · 3c Growth · 3d Camera Setup). 원본 그대로. |

턴 1(레이아웃 3안: 1a Console 사이드바 · 1b Mission Control 초대형 타이포 · 1c Bench 크림 캔버스)과
턴 2(Colbo 무드: 반원 바늘 게이지 · sage/clay 뮤트 팔레트)는 탐색안이라 여기 두지 않는다. 원본 프로젝트에서 확인.

## 목업 → 코드 매핑 (web/)

| 목업 값 | 토큰 / 컴포넌트 |
|---|---|
| 캔버스 #173046 · 헤더/프리뷰 #122839 · 카드 #1E3A54 | `--bg` · `--bg-sunken` · `--bg-elev` (`web/src/styles/tokens.css`, dark 가 기본) |
| 글자 #F2F2F2 · 보조 #C0C0C0 · 액센트 #D84C27 · 버튼 #2C5979 | `--ink` · `--ink-muted` · `--accent` · `--btn` |
| stable #7FB3D8(칩 글자 #173046) · fluct #D84C27(글자 #E88A6C) | `--stable/--stable-on/--stable-ink` · `--fluct/--fluct-on/--fluct-ink`, `TreatPill` |
| Space Grotesk, tabular-nums, 카드 radius 16 / 14 | `--font-sans`(Space Grotesk → Pretendard 폴백) · `--r-lg` |
| `plantlab°` 워드마크, 대문자 트래킹 내비 + 액센트 밑줄, "4 nodes · Day 14/42 · 18:04 KST" | `TopBar`, `.nav-item`, `useRunStatus` |
| 3a 니들 게이지 5종 | `GaugeTile`, `lib/env.ts`(범위·OPTIMAL 밴드) |
| 3a 토양수분 밴드 · Treatment check · 급수 이벤트 | `SoilBandCard` · `TreatmentCheckCard` · `PumpEventsCard` |
| 3a "허전함" 보강 | `WaterCard`(관수 기록) · `CaptureLogCard`(촬영 일지) |
| 3b KPI 3종 · 수분 궤적 · 밴드 설정(raw) · 수분 분포 | `TreatKpiRow` · `TrajectoryCard` · `BandSettingsCard` · `HistogramCard(compact)` |
| 3c DAWN/PM/MASK 칩 · 3×2 화분 카드 · RGR 추이 · ΔRGR | `PhaseChips` · `PotGrid` · `RgrTrendCard` · `DeltaRgrCard` |
| 3d 프리뷰 + 5단계 레일 · 저장 → config.json | `CameraSetupPage` · `VStepper/StepBadge` · `StageOverlays`(ROI 색 = 처리군) |

목업에 없는 기존 기능(톱니 차트, 관수 표, forest plot, 처짐, 시스템 페이지)은 같은 토큰으로 아래에 이어진다.
