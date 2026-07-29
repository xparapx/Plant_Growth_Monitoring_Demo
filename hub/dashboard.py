"""
dashboard.py — Lettuce Variance Trial monitor
  uv run streamlit run dashboard.py --server.address 0.0.0.0 --server.port 8501

레이아웃은 노드 수에 맞춰 자동으로 잡힙니다 — 처리군별로 묶여 배치되므로
화분을 늘리거나 줄여도 코드를 고칠 필요가 없습니다.

■ 다크 테마 — config.toml 없이 이 파일 하나로 처리합니다. 3중으로 겁니다.
  (1) 런타임 테마 옵션   : 비공개 API. 캔버스로 그려져 CSS가 닿지 않는 요소까지 커버.
                          버전에 따라 실패할 수 있어 try 로 감쌌고, 실패해도 (2)(3)이 받칩니다.
  (2) CSS 변수 재정의    : Streamlit 내부 --text-color 등을 덮어써 기본 글자색을 화이트로.
                          인라인 색상은 건드리지 않으므로 처리군 식별색은 그대로 삽니다.
  (3) Plotly layout.font : BLANK 에 넣어 모든 그래프의 축·범례·subplot 제목을 화이트 고정.
  · st.dataframe(캔버스 렌더링)은 CSS로 색을 바꿀 수 없어 HTML 표로 대체했습니다.
"""
import json, sqlite3
import numpy as np, pandas as pd, streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh

# ══════════════ 설정 ══════════════
DB        = "plant.db"
TZ        = 9            # UTC -> KST
TOL       = 2.0          # 평균 정렬 허용폭 (%p)
DEMO_FILL = True         # ★ 비어 있는 테이블을 가상 데이터로 채워 레이아웃을 확인.
                         #    실제 운용에 들어가면 False 로 바꾸세요.
# ═════════════════════════════════

# ── (1) 런타임 테마 강제 ───────────────────────────────────
#   set_page_config 보다 먼저, 어떤 위젯보다도 먼저 호출해야 합니다.
#   OS/브라우저가 라이트모드여도 Streamlit 이 다크로 고정됩니다.
def _force_dark_theme():
    opts = {"theme.base": "dark",
            "theme.backgroundColor": "#0E1117",
            "theme.secondaryBackgroundColor": "#1A1D24",
            "theme.textColor": "#FFFFFF",
            "theme.primaryColor": "#82C8E5"}
    cfg = getattr(st, "_config", None)
    if cfg is None:
        try:
            from streamlit import config as cfg          # 구버전 경로
        except Exception:
            return
    for k, v in opts.items():
        try:
            cfg.set_option(k, v)
        except Exception:
            pass                                          # 실패해도 CSS 가 받칩니다
_force_dark_theme()

# ── 팔레트 ────────────────────────────────────────────────
#   어두운 배경 · 흰 글자.
#   라이트 테마와 명암 관계가 뒤집힙니다 — 면(막대·분포·실루엣)에는 원색을,
#   선·글자에는 원색보다 <b>더 밝은</b> 변형을 씁니다. (라이트 테마에서는 더 짙은 변형)
STABLE,   FLUCT   = "#82C8E5", "#F88379"     # 처리군 — 푸른 / 핑크 (면)
STABLE_B, FLUCT_B = "#A9DEF5", "#FFA79C"     # 선·텍스트용 (밝은 변형)
LEAF = "#A8BA72"                              # 식생 — 세이지
OK, BAD, MUT, RULE = "#7CC46A", "#F2685A", "#A79E93", "#2E323B"
INK  = "#FFFFFF"                              # 모든 그래프·표의 기본 글자색
ENV_C = dict(vpd="#4FB8CF", temp="#F08A6E", hum="#7FB8D6",
             co2="#B4C77A", lux="#F5C445")    # 환경 5종 — 처리군 색과 구분되게
LW = dict(trace=2.2, growth=3.0, spark=2.2, curve=3.0)   # 선 굵기
CT   = {"stable": STABLE,   "fluct": FLUCT}       # 면
CD   = {"stable": STABLE_B, "fluct": FLUCT_B}     # 선·글자
NAME = {"stable": "STABLE", "fluct": "FLUCTUATING"}

st.set_page_config(page_title="Lettuce Variance Trial", layout="wide")
st_autorefresh(interval=60_000, key="tick")

# ── (2) CSS ───────────────────────────────────────────────
st.markdown("""<style>
 :root, .stApp{
   --bg:#0E1117; --card:#1A1D24; --ink:#FFFFFF; --mut:#9AA1AC; --rule:#2E323B;
   /* Streamlit 내부 테마 변수를 직접 덮어씁니다. 컴포넌트 기본 글자색만 바뀌고
      인라인 style 로 준 처리군 색상은 그대로 유지됩니다. */
   --text-color:#FFFFFF!important;
   --background-color:#0E1117!important;
   --secondary-background-color:#1A1D24!important;
 }
 .stApp{background:#0E1117; color:#FFF}
 [data-testid="stHeader"]{background:transparent}
 [data-testid="stToolbar"]{color:#FFF}
 .block-container{padding-top:1.1rem;max-width:1500px}

 /* 라이트 테마에서 검게 렌더링되던 텍스트만 화이트 고정.
    광역 규칙(.stApp div{color:#FFF!important})은 쓰지 않습니다 —
    처리군 식별색·판정색까지 죽습니다. */
 [data-testid="stMetricValue"]{font-size:23px;font-family:ui-monospace,monospace;color:#FFF!important}
 [data-testid="stMetricLabel"],[data-testid="stMetricLabel"] p{
    font-size:10px;letter-spacing:.11em;text-transform:uppercase;color:#FFF!important}
 [data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p,
 .stTabs [data-baseweb="tab"],.stTabs [data-baseweb="tab"] p,
 summary,summary p,[data-testid="stExpander"] p,[data-testid="stExpander"] summary,
 [data-testid="stAlert"] p,[data-testid="stNotification"] p,
 label,label p,.stDownloadButton button{color:#FFF!important}
 .stMarkdown p,.stMarkdown li,
 .stApp h1,.stApp h2,.stApp h4,.stApp h5,.stApp h6{color:#FFF}
 h3{font-size:11px!important;letter-spacing:.12em;text-transform:uppercase;color:var(--mut);
    margin:14px 0 4px!important;font-weight:700!important}

 .chip{display:inline-flex;align-items:center;gap:7px;background:var(--card);border:1px solid var(--rule);
       border-radius:3px;padding:5px 9px;margin-right:6px;font-size:11px;color:#FFF}
 .chip.bad{border-color:#8C3B31;background:#2B1614}
 .chip .d{width:7px;height:7px;border-radius:50%}
 .chip b{font-weight:650}
 .chip s{text-decoration:none;color:var(--mut);font-family:ui-monospace,monospace;font-size:9.5px}
 .alert{background:#2B1614;border:1px solid #6E322A;color:#FFB4A8;border-radius:3px;
        padding:7px 11px;margin:5px 0;font-size:12.5px}
 .demo{display:inline-block;background:#2A2415;border:1px solid #6B5A28;color:#E8D9A8;
       border-radius:2px;padding:1px 7px;font-size:9.5px;font-weight:700;letter-spacing:.09em;
       margin-left:7px;vertical-align:2px}
 .grp{font-size:10px;font-weight:700;letter-spacing:.12em;color:#9AA1AC;margin:6px 0 2px}

 /* st.dataframe 대체용 표 — 캔버스가 아니라 DOM 이라 색이 확실히 잡힙니다 */
 .tbl{width:100%;border-collapse:collapse;font-size:12px;color:#FFF;background:transparent;
      margin-top:2px}
 .tbl th{text-align:left;font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;
         color:#FFF;font-weight:700;border-bottom:1px solid #3A3F4A;padding:6px 9px;
         white-space:nowrap}
 .tbl td{color:#FFF;border-bottom:1px solid #22262E;padding:6px 9px;
         font-family:ui-monospace,monospace;white-space:nowrap}
 .tbl tr:hover td{background:#1A1D24}
</style>""", unsafe_allow_html=True)


# ── (3) Plotly ────────────────────────────────────────────
# 모든 그래프가 **BLANK 를 펼쳐 쓰므로, font 한 줄이면 축 눈금·범례·subplot 제목까지
# 전부 화이트로 고정됩니다. 명시적 layout.font.color 는 Streamlit 테마 템플릿보다 우선합니다.
# 배경은 투명 — 페이지의 다크 배경이 그대로 비칩니다.
BLANK = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
             font=dict(color=INK))


def html_table(df):
    """st.dataframe 은 <canvas> 로 그려져 CSS 로 글자색을 바꿀 수 없습니다.
    행 수가 적은 표는 DOM 으로 직접 그립니다."""
    th = "".join(f"<th>{c}</th>" for c in df.columns)
    tr = "".join("<tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr>"
                 for row in df.astype(str).itertuples(index=False))
    st.markdown(f'<table class="tbl"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>',
                unsafe_allow_html=True)


# BME688(온·습·기압·VPD)이 빠져도 노드는 0 을 발행합니다.
# 0 을 그대로 그리면 <센서가 없는 것>과 <진짜 0>을 구별할 수 없습니다.
# 6주 중간에 센서가 죽어도 아무도 모르게 되므로, 여기서 결측으로 판정합니다.
BME_KEYS = ("temp", "hum", "press", "vpd")


def missing(env, key):
    """이 값이 실측인지 아닌지. 결측이면 True."""
    v = env[key].tail(12)
    if v.isna().all():
        return True
    if key in BME_KEYS:                       # 온·습이 동시에 0 이면 센서 미연결
        t, hgh = env["temp"].tail(12), env["hum"].tail(12)
        if (t.abs() < 0.05).all() and (hgh.abs() < 0.05).all():
            return True
    return False


def render_env(env):
    cur = env.iloc[-1]; day = env.iloc[max(0, len(env) - 288)]
    gone = []
    for col, (lbl, key, unit, fmt, color) in zip(st.columns(5), [
            ("VPD", "vpd", "kPa", "{:.2f}", ENV_C["vpd"]),
            ("Temp", "temp", "°C", "{:.1f}", ENV_C["temp"]),
            ("RH", "hum", "%", "{:.0f}", ENV_C["hum"]),
            ("CO₂", "co2", "ppm", "{:.0f}", ENV_C["co2"]),
            ("Light", "lux", "lx", "{:,.0f}", ENV_C["lux"])]):
        with col:
            if missing(env, key):
                gone.append(lbl)
                st.metric(lbl, "—", "센서 없음", delta_color="off")
                st.plotly_chart(spark(env[key].tail(288) * 0, MUT), use_container_width=True,
                                config={"displayModeBar": False}, key=f"env_{key}")
            else:
                st.metric(lbl, fmt.format(cur[key]),
                          fmt.format(cur[key] - day[key]) if key != "lux" else None,
                          delta_color="off")
                st.plotly_chart(spark(env[key].tail(288), color), use_container_width=True,
                                config={"displayModeBar": False}, key=f"env_{key}")
    if gone:
        st.markdown(
            f'<div class="alert">! &nbsp;<b>{", ".join(gone)}</b> 가 실측이 아닙니다 — '
            f'BME688 미연결이거나 읽기 실패입니다. '
            f'<b>0 이 아니라 결측</b>으로 기록되도록 노드 펌웨어를 고치세요.</div>',
            unsafe_allow_html=True)


def spark(y, color, h=60):
    f = go.Figure(go.Scatter(y=y, mode="lines", line=dict(color=color, width=LW["spark"]),
                             hoverinfo="skip"))
    f.update_layout(height=h, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
                    xaxis=dict(visible=False), yaxis=dict(visible=False), **BLANK)
    return f


# ═══════════════ 데이터 ═══════════════
@st.cache_data(ttl=55)
def q(sql):
    try:
        with sqlite3.connect(DB) as c:
            df = pd.read_sql_query(sql, c)
    except Exception:
        return pd.DataFrame()
    if "ts" in df and len(df):
        df["ts"] = pd.to_datetime(df["ts"]) + pd.Timedelta(hours=TZ)
    return df


# ★ firmware/water_node.ino 의 RAW_ON / RAW_OFF 와 반드시 같아야 합니다.
BAND_RAW = {"stable": (1900, 1940), "fluct": (1820, 2020)}   # (젖음, 마름) raw
CAL = {"_default": (2120, 1750)}          # plant_id -> (RAW_DRY, RAW_WET)


def pct_of(raw, pid="_default"):
    dry, wet = CAL.get(pid, CAL["_default"])
    return 100.0 * (dry - raw) / float(dry - wet)


BAND = {t: (pct_of(hi), pct_of(lo)) for t, (lo, hi) in BAND_RAW.items()}

@st.cache_data(ttl=600)
def synth(roster=None, days=7, step_min=30):
    """레이아웃 확인용 가상 데이터.

    roster 가 주어지면 <b>실제 화분 ID·처리군을 그대로 따릅니다.</b>
    카메라만 붙인 상태에서도 실측 캐노피와 가상 토양수분이 <b>같은 화분으로</b> 이어집니다.
    """
    rng = np.random.default_rng(7)
    n   = days * 24 * 60 // step_min
    t0  = pd.Timestamp.now().floor("h") - pd.Timedelta(minutes=step_min * (n - 1))
    ts  = [t0 + pd.Timedelta(minutes=step_min * i) for i in range(n)]
    if roster:
        pots = [(pid, tr, *BAND.get(tr, (30, 55))) for pid, tr in sorted(roster.items())]
    else:
        pots = [(f"p{i}", t, *BAND[t]) for i, t in
                enumerate(["stable"] * 3 + ["fluct"] * 3, 1)]

    soil, pump = [], []
    for k, (pid, tr, on, off) in enumerate(pots):
        v, filling = off - rng.uniform(0, 3), False
        for i in range(n):
            hh = ts[i].hour
            rate = (0.55 if 7 <= hh < 19 else 0.12) * (1 + 0.10 * (k % 3 - 1))
            if filling:
                v += 4.5
                if v >= off: v, filling = off, False
            else:
                v -= rate * (step_min / 30) * rng.uniform(.85, 1.15)
                if v <= on:
                    filling = True
                    pump.append(dict(ts=ts[i], node=pid, plant_id=pid, treat=tr,
                                     dur_ms=int(rng.uniform(2400, 3600)),
                                     soil_before=round(v, 1), soil_after=float(off),
                                     reason="filled"))
            soil.append(dict(ts=ts[i], node=pid, plant_id=pid, treat=tr,
                             pct=round(v + rng.normal(0, .25), 2), n=30))
    soil = pd.DataFrame(soil)
    # 고장 시나리오 2종 — 경보 표시 확인용
    ids = [x[0] for x in pots]
    if len(ids) >= 5:                                       # 경보 표시 확인용
        m = (soil.plant_id == ids[4]) & (soil.ts >= ts[-12])
        soil.loc[m, "pct"] = float(soil.loc[m, "pct"].iloc[0])
    if len(ids) >= 2:
        pump.append(dict(ts=ts[-40], node=ids[1], plant_id=ids[1], treat=pots[1][1],
                         dur_ms=3000, soil_before=37.8, soil_after=38.0, reason="verify_fail"))

    def blob(R, seed, k=9):
        r = np.random.default_rng(seed)
        ph, ph2 = r.uniform(0, 6.3, 2)
        a = np.arange(0, 6.2832, .1)
        rad = R * (1 + .16 * np.sin(k * a + ph) + .09 * np.sin(2 * k * a + ph2))
        return json.dumps([[round(float(rad[i] * np.cos(a[i])), 1),
                            round(float(rad[i] * np.sin(a[i])), 1)] for i in range(len(a))])

    grow = []
    for d in range(days):
        for k, (pid, tr, *_) in enumerate(pots):
            base = (11.5 * np.exp(.145 * d) if tr == "stable" else 11.3 * np.exp(.131 * d))
            base *= 1 + rng.normal(0, .05)
            droop = rng.uniform(2, 5) if tr == "stable" else rng.uniform(9, 17)
            for phase, mult, hour in (("dawn", 1.0, 6), ("pm", 1 - droop / 100, 15)):
                area = base * mult
                grow.append(dict(ts=t0.normalize() + pd.Timedelta(days=d, hours=hour),
                                 plant_id=pid, treat=tr, phase=phase,
                                 area_cm2=round(area, 2), area_px=int(area * 900),
                                 px_per_cm=30.0, img_file="", ok=1,
                                 contour=blob(30 * np.sqrt(area / 11.5), k * 13 + 3)))
    return soil, pd.DataFrame(pump).sort_values("ts", ascending=False), pd.DataFrame(grow)


env  = q("SELECT * FROM readings ORDER BY ts")
soil = q("SELECT * FROM soil WHERE ts > datetime('now','-7 day') ORDER BY ts")
pump = q("SELECT * FROM pump_log ORDER BY ts DESC LIMIT 200")
grow = q("SELECT * FROM growth WHERE ok=1 ORDER BY ts")

def roster_of(*dfs):
    """실측 테이블에서 화분 목록(ID -> 처리군)을 모읍니다."""
    fr = [d[["plant_id", "treat"]] for d in dfs if len(d) and "plant_id" in d.columns]
    return pd.concat(fr).dropna().groupby("plant_id").treat.last().to_dict() if fr else {}


def treat_sources(soil_df, grow_df):
    """화분별 처리군을 <출처를 구분해서> 모읍니다.
       soil.treat  <- 급수 펌웨어가 보낸 값
       growth.treat<- config.json 의 rois[].treat
       roster_of() 는 둘을 합쳐 .last() 로 하나만 남깁니다. 다르면 경고 없이
       뒤쪽(config.json)이 이깁니다 -> 첫 촬영 날 그룹이 조용히 뒤집힙니다."""
    out = {}
    for src, d in (("펌웨어(soil)", soil_df), ("config.json(growth)", grow_df)):
        if len(d) and "plant_id" in d.columns:
            last = d[["plant_id", "treat"]].dropna().groupby("plant_id").treat.last()
            for pid, tr in last.items():
                out.setdefault(pid, {})[src] = tr
    return out


# 실측으로 들어온 화분·노드를 먼저 기록해 둡니다 (데모로 채우기 전에).
REAL_POTS = set(roster_of(soil, grow))
REAL_ENV  = not env.empty

FAKE = set()
if DEMO_FILL:
    s2, p2, g2 = synth(roster_of(soil, grow) or None)      # ★ 실측 화분에 맞춰 생성
    if soil.empty: soil, _ = s2, FAKE.add("soil")
    if pump.empty: pump, _ = p2, FAKE.add("pump")
    if grow.empty: grow, _ = g2, FAKE.add("growth")
    if env.empty:
        FAKE.add("env")
        env = pd.DataFrame(dict(
            ts=soil.ts.unique(),
            temp=21 + 4 * np.sin(np.arange(soil.ts.nunique()) / 24), hum=60.0,
            press=1013.0, vpd=1.2, co2=600.0, lux=8000.0, n=30))

if soil.empty:
    # 노드가 아직 없어도 있는 것만이라도 보여줍니다.
    if env.empty:
        st.warning("No data yet. Start hub.py, then power a node.")
    else:
        st.markdown("### Environment")
        render_env(env)
        st.info("Water and camera nodes are not connected yet — those sections appear "
                "automatically once they publish. Set DEMO_FILL = True to preview the full "
                "layout with demo data.")
    st.stop()

BADGE = '<span class="demo">DEMO DATA</span>'
def head(title, fake_key=None):
    st.markdown(f"### {title}" + (BADGE if fake_key in FAKE else ""), unsafe_allow_html=True)

if FAKE:
    st.markdown(
        f'<div class="alert">! &nbsp;<b>DEMO DATA</b> — <b>{", ".join(sorted(FAKE))}</b>'
        f'는 가상의 데이터이며 해당 노드 연결 시 실측값으로 변경 반영</div>',
        unsafe_allow_html=True)

# 처리군별 묶음 — 노드가 늘거나 줄어도 레이아웃이 따라옵니다
TREAT  = roster_of(soil, grow)                             # soil·growth 양쪽에서 수집
POTS   = sorted(TREAT)

# 처리군 라벨은 'stable' | 'fluct' 만 인정합니다.
# (통신 테스트 때 쏜 treat="A" 같은 잔여 행이 섞이면 여기서 걸립니다)
UNKNOWN = sorted({v for v in TREAT.values() if v not in ("stable", "fluct")})
if UNKNOWN:
    st.error(f"Unrecognised treatment label(s): {UNKNOWN}. "
             f"Expected 'stable' or 'fluct'. These rows are probably left over from an MQTT "
             f"test — delete them, e.g.  DELETE FROM soil WHERE treat IN "
             f"({', '.join(repr(u) for u in UNKNOWN)});")
    TREAT = {k: v for k, v in TREAT.items() if v in ("stable", "fluct")}
    POTS  = sorted(TREAT)
# ── ★ 처리군 출처 충돌 — 07-28 유형 사고를 화면에서 잡습니다 ────────────
#   같은 화분인데 펌웨어가 말하는 처리군과 config.json 이 말하는 처리군이 다르면,
#   둘 중 하나는 반드시 틀렸습니다. 어느 쪽이 틀렸는지는 데이터로 알 수 없으므로
#   (물은 펌웨어대로 주고, 라벨은 config.json 대로 붙습니다) 화면이 판단하지 않고
#   <그 화분을 그리지 않고> 사람에게 넘깁니다. 틀린 그룹으로 그린 그래프보다 낫습니다.
SRC      = treat_sources(soil, grow)
CONFLICT = {p: v for p, v in SRC.items() if len(set(v.values())) > 1}
if CONFLICT:
    rows = "".join(
        f"<tr><td><b>{p}</b></td>"
        + "".join(f"<td>{s} → <b>{t}</b></td>" for s, t in sorted(v.items()))
        + "</tr>"
        for p, v in sorted(CONFLICT.items()))
    st.markdown(
        '<div class="alert">! &nbsp;<b>처리군 불일치 — 이 화분들은 그리지 않습니다</b><br>'
        '<table style="margin:6px 0">' + rows + '</table>'
        '펌웨어와 <code>config.json</code> 이 서로 다른 처리군을 말하고 있습니다. '
        '<b>펌프 호스가 실제로 꽂힌 화분</b>을 기준으로 어느 쪽이 맞는지 정한 뒤, '
        '<code>water_node.ino</code> 의 <code>TREAT_FLUCT</code>·<code>PLANT_ID</code> 와 '
        '<code>config.json</code> 의 <code>rois[].treat</code> 를 맞추세요.<br>'
        '<b>과거 행을 지우기 전에 반드시 <code>plant.db</code> 를 백업하세요.</b>'
        '</div>', unsafe_allow_html=True)
    TREAT = {k: v for k, v in TREAT.items() if k not in CONFLICT}
    POTS  = sorted(TREAT)

GROUPS = {t: [p for p in POTS if TREAT.get(p) == t] for t in ("stable", "fluct")}
GROUPS = {t: v for t, v in GROUPS.items() if v}
NCOL   = max((len(v) for v in GROUPS.values()), default=1)
NROW   = NCOL                                              # 톱니 subplot 행 수
# 가장 최근 수신 시각 — 한 테이블에만 오래된 행이 있어도 경과시간이 음수가 되지 않게
now    = max(d.ts.max() for d in (env, soil, pump, grow) if len(d) and "ts" in d.columns)

tab_ov, tab_tx, tab_gr = st.tabs(["OVERVIEW", "TREATMENT", "GROWTH"])


# ═══════════════ OVERVIEW ═══════════════
with tab_ov:
    head("Environment", "env")
    render_env(env)

    st.markdown("### Nodes")
    chips, alerts = [], []
    def chip(name, mins, stuck=False, every=5, real=True):
        """실측 노드만 상태로 판정합니다. 없는 노드를 초록으로 띄우면 안 됩니다."""
        if not real:
            chips.append(f'<span class="chip" style="opacity:.55">'
                         f'<span class="d" style="background:#5A6169"></span>'
                         f'<b>{name}</b><s>not connected</s></span>')
            return
        bad = stuck or mins > every * 12
        c = BAD if bad else ("#E8B44A" if mins > every * 4 else OK)
        s = "value stuck" if stuck else (f"{mins}m" if mins < 60 else f"{mins//60}h {mins%60}m")
        chips.append(f'<span class="chip {"bad" if bad else ""}">'
                     f'<span class="d" style="background:{c}"></span><b>{name}</b><s>{s}</s></span>')

    chip("ENV", int((now - env.ts.max()).total_seconds() // 60), real=REAL_ENV)
    for p in POTS:
        real = p in REAL_POTS
        s = soil[soil.plant_id == p]
        tail = s.pct.tail(12)
        stuck = real and len(tail) >= 12 and tail.nunique() == 1   # 흙은 계속 마름 -> 값 고정 = 고장
        chip(p.upper(), int((now - s.ts.max()).total_seconds() // 60), stuck, real=real)
        if stuck:
            alerts.append(f"<b>{p.upper()} — value unchanged, node still transmitting.</b> "
                          f"Irrigation is running on a dead reading. Check I2C lead.")
    chip("CAM", int((now - grow.ts.max()).total_seconds() // 60) if not grow.empty else 0,
         every=720, real="growth" not in FAKE and not grow.empty)
    vf = pump[pump.reason == "verify_fail"].plant_id.unique() if "reason" in pump else []
    vf = [v for v in vf if v in REAL_POTS]                          # 데모 고장은 경보하지 않음
    if len(vf):
        alerts.append(f"<b>{', '.join(v.upper() for v in vf)} — pump ran, no moisture rise.</b> "
                      f"Node disarmed. Check tube and tank.")
    if not alerts and REAL_POTS:
        st.session_state["_ok"] = True
    st.markdown("".join(chips), unsafe_allow_html=True)
    for a in alerts:
        st.markdown(f'<div class="alert">! &nbsp;{a}</div>', unsafe_allow_html=True)

    head("Validity", "soil")
    g = soil.groupby(soil.plant_id.map(TREAT)).pct
    mu, sd = g.mean(), g.std()                 # 두 탭에서 함께 쓰므로 항상 계산
    if len(GROUPS) < 2:
        st.info("Needs both treatment groups (stable and fluctuating) to judge validity.")
    else:
        dmu   = abs(mu["stable"] - mu["fluct"])
        ratio = sd["fluct"] / sd["stable"]
        v1, v2 = st.columns([1.4, 1])
        with v1:
            st.metric("Mean alignment  Δμ = |μs − μf|", f"{dmu:.2f} %p",
                      "ALIGNED" if dmu <= TOL else "DRIFT",
                      delta_color="normal" if dmu <= TOL else "inverse")
            f = go.Figure()
            f.add_vrect(x0=mu["stable"] - TOL / 2, x1=mu["stable"] + TOL / 2,
                        fillcolor=OK, opacity=.16, line_width=0)
            for k in GROUPS:
                f.add_trace(go.Scatter(x=[mu[k]], y=[0], mode="markers+text",
                                       text=[f"{k[0].upper()} {mu[k]:.1f}"],
                                       textposition="top center",
                                       marker=dict(size=15, color=CT[k],
                                                   line=dict(color=CD[k], width=2)),
                                       textfont=dict(color=CD[k], size=12),
                                       showlegend=False))
            f.update_layout(height=110, margin=dict(l=6, r=6, t=22, b=4),
                            xaxis=dict(range=[mu.min() - 5, mu.max() + 5]),
                            yaxis=dict(visible=False, range=[-.5, .8]), **BLANK)
            st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False}, key="validity_mean")
        with v2:
            st.metric("Variance ratio  σf / σs", f"{ratio:.2f} ×",
                      "SEPARATED" if ratio >= 2 else "TOO CLOSE",
                      delta_color="normal" if ratio >= 2 else "inverse")
            f = go.Figure(go.Bar(x=[sd[k] for k in GROUPS], y=[k[0].upper() for k in GROUPS],
                                 orientation="h",
                                 marker=dict(color=[CT[k] for k in GROUPS],
                                             line=dict(color=[CD[k] for k in GROUPS], width=1.5)),
                                 text=[f"σ {sd[k]:.2f}" for k in GROUPS], textposition="outside",
                                 textfont=dict(color=INK)))
            f.update_layout(height=110, margin=dict(l=6, r=40, t=8, b=4), showlegend=False,
                            xaxis=dict(visible=False), **BLANK)
            st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False}, key="validity_var")

    # ── 캐노피 오버레이 : 처리군당 한 줄 ──
    head("Canopy projected area — 3 d ago → now", "growth")
    dawn = grow[grow.phase == "dawn"] if "phase" in grow else grow
    if dawn.empty or "contour" not in dawn:
        st.caption("Waiting for camera. leafcv.py must publish `contour`.")
    else:
        for treat, members in GROUPS.items():
            st.markdown(f'<div class="grp" style="color:{CD[treat]}">{NAME[treat]}</div>',
                        unsafe_allow_html=True)
            cols = st.columns(NCOL)                    # 군끼리 열 너비를 맞춤
            for col, p in zip(cols, members):
                d = dawn[(dawn.plant_id == p)].dropna(subset=["contour"])
                if len(d) < 2:
                    col.caption(f"{p.upper()} — not enough frames"); continue
                new = d.iloc[-1]
                older = d[d.ts <= new.ts - pd.Timedelta(days=3)]
                old = older.iloc[-1] if len(older) else d.iloc[0]
                gain = 100 * (new.area_px - old.area_px) / old.area_px
                c = CT[treat]
                f = go.Figure()
                # 어두운 배경에서는 낮은 불투명도가 더 많이 죽습니다 — 3d 전 실루엣을 조금 올렸습니다.
                for row, op, w in [(old, .34, 0), (new, .72, 2.6)]:
                    xy = np.array(json.loads(row.contour))
                    f.add_trace(go.Scatter(x=xy[:, 0], y=xy[:, 1], fill="toself", fillcolor=c,
                                           opacity=op, mode="lines",
                                           line=dict(color=CD[treat], width=w), hoverinfo="skip"))
                lim = float(np.abs(np.array(json.loads(new.contour))).max()) * 1.12
                f.update_layout(height=150, margin=dict(l=0, r=0, t=22, b=0), showlegend=False,
                                title=dict(text=f"<b>{p.upper()}</b>  "
                                                f"<span style='color:{CD[treat]}'>+{gain:.0f}%</span>",
                                           font=dict(size=12, color=INK), x=0, y=.97),
                                xaxis=dict(visible=False, range=[-lim, lim]),
                                yaxis=dict(visible=False, range=[-lim, lim], scaleanchor="x"), **BLANK)
                col.plotly_chart(f, use_container_width=True, config={"displayModeBar": False},
                                 key=f"canopy_{treat}_{p}")
                col.caption(f"{old.area_cm2:.1f} → {new.area_cm2:.1f} cm²")

    # ── 톱니 : 좌 STABLE / 우 FLUCTUATING ──
    head("Wetting–drying cycles — 7 d", "soil")
    if not GROUPS:
        st.info("No pots with a recognised treatment yet.")
        st.stop()
    nrow = max(len(v) for v in GROUPS.values())
    # 예전 range=[15,68] 은 synth() 가짜데이터(22~62)용이라 실제 fluct(27~81)가 잘렸습니다.
    lo = min([soil.pct.min()] + [b[0] for b in BAND.values()])
    hi = max([soil.pct.max()] + [b[1] for b in BAND.values()])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo, hi = 20.0, 85.0
    pad = max(2.0, (hi - lo) * .06)
    YR = [max(0.0, lo - pad), min(100.0, hi + pad)]
    f = make_subplots(rows=nrow, cols=len(GROUPS), shared_xaxes=True, shared_yaxes=True,
                      vertical_spacing=.02, horizontal_spacing=.05,
                      subplot_titles=[NAME[t] for t in GROUPS] + [""] * (nrow - 1) * len(GROUPS))
    for ci, (treat, members) in enumerate(GROUPS.items(), 1):
        blo, bhi = BAND[treat]
        for ri, p in enumerate(members, 1):
            f.add_hrect(y0=blo, y1=bhi, row=ri, col=ci, layer="below",
                        fillcolor=CD[treat], opacity=.10, line_width=0)
            s = soil[soil.plant_id == p]
            f.add_trace(go.Scatter(x=s.ts, y=s.pct, mode="lines",
                                   line=dict(color=CD[treat], width=LW["trace"]), showlegend=False,
                                   name=p.upper()), row=ri, col=ci)
            f.update_yaxes(title_text=f"<b>{p.upper()}</b>", range=YR,
                           title_font=dict(size=10, color=CD[treat]),
                           showticklabels=(ci == 1), row=ri, col=ci)
    f.update_layout(height=118 * nrow + 30, margin=dict(l=46, r=10, t=26, b=24), **BLANK)
    f.update_xaxes(gridcolor=RULE); f.update_yaxes(gridcolor=RULE)
    for a in f.layout.annotations: a.font.size = 11; a.font.color = INK
    st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False}, key="soil_saw")

    head("Recent irrigation", "pump")
    if not pump.empty:
        t = pump.head(5).copy()
        t["Ago"]    = ((now - t.ts).dt.total_seconds() // 3600).astype(int).astype(str) + "h"
        t["Pot"]    = t.plant_id.str.upper()
        t["Trt"]    = t.plant_id.map(TREAT).str.upper()
        t["Pump"]   = (t.dur_ms / 1000).round(1).astype(str) + "s"
        t["Before"] = t.soil_before.round(1)
        t["After"]  = t.soil_after.round(1)
        t["Rise"]   = (t.soil_after - t.soil_before).round(1)
        t["Reason"] = t.reason
        html_table(t[["Ago", "Pot", "Trt", "Pump", "Before", "After", "Rise", "Reason"]])


# ═══════════════ TREATMENT ═══════════════
with tab_tx:
    head("Soil moisture distribution ρ(w) — measured", "soil")
    f = go.Figure()
    for k in GROUPS:
        v = soil[soil.plant_id.map(TREAT) == k].pct
        f.add_trace(go.Histogram(
            x=v, nbinsx=44, histnorm="probability",
            marker=dict(color=CT[k], line=dict(color=CD[k], width=1)),
            opacity=.55 if k == "fluct" else .70,
            name=f"{NAME[k].title()}  μ={v.mean():.1f}  σ={v.std():.1f}"))
    if len(GROUPS) == 2:
        f.add_vline(x=float(np.mean([mu[k] for k in GROUPS])),
                    line=dict(color=INK, width=1, dash="dot"),
                    annotation_text="E[w]", annotation_position="top",
                    annotation_font=dict(color=INK))
    f.update_layout(height=300, barmode="overlay", margin=dict(l=52, r=16, t=8, b=42),
                    legend=dict(orientation="h", y=1.12, font=dict(size=11, color=INK)),
                    xaxis_title="soil moisture w (%)", yaxis_title="ρ(w)", **BLANK)
    f.update_yaxes(gridcolor=RULE); f.update_xaxes(gridcolor=RULE)
    st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False}, key="dist")
    st.caption("Treatment check: same centre, different width. This is measured data.")

    # ── 해석 참조: 어느 쪽인지는 실험이 정합니다 (데이터 아님) ──
    with st.expander("How to read the result — reference, not data"):
        w = np.linspace(15, 70, 200)
        lo, hi = float(soil.pct.quantile(.05)), float(soil.pct.quantile(.95))
        m = float(soil.pct.mean())
        cc = make_subplots(rows=1, cols=2, horizontal_spacing=.09, subplot_titles=[
            "∩ concave  →  FLUCTUATING LOSES", "∪ convex  →  FLUCTUATING GAINS"])
        for ci, fw in enumerate(
                [100 * (1 - np.exp(-2.6 * np.clip((w - 18) / 44, 0, None))),
                 100 * np.clip((w - 15) / 55, 0, None) ** 2.2], 1):
            gm  = float(np.interp(m, w, fw))
            ch  = float(np.mean([np.interp(lo, w, fw), np.interp(hi, w, fw)]))
            col = STABLE_B if ci == 1 else FLUCT_B
            cc.add_trace(go.Scatter(x=w, y=fw, mode="lines",
                                    line=dict(color=MUT, width=LW["curve"]),
                                    showlegend=False), row=1, col=ci)
            cc.add_trace(go.Scatter(x=[lo, hi], y=[np.interp(lo, w, fw), np.interp(hi, w, fw)],
                                    mode="lines", line=dict(color=MUT, width=1.2, dash="dash"),
                                    showlegend=False), row=1, col=ci)
            cc.add_trace(go.Scatter(x=[m, m], y=[ch, gm], mode="lines+markers",
                                    line=dict(color=col, width=2.5), marker=dict(size=8),
                                    showlegend=False), row=1, col=ci)
        cc.update_layout(height=230, margin=dict(l=40, r=14, t=34, b=30), **BLANK)
        cc.update_xaxes(title_text="w (%)", gridcolor=RULE)
        cc.update_yaxes(title_text="growth", gridcolor=RULE, row=1, col=1)
        for a in cc.layout.annotations: a.font.size = 11; a.font.color = INK
        st.plotly_chart(cc, use_container_width=True, config={"displayModeBar": False}, key="curves")
        st.caption("Both shapes are drawn on purpose. **Which one lettuce follows is unknown — "
                   "that is what this experiment measures.** Neither curve is fitted to your data; "
                   "the experiment returns the *sign* of the curvature, not the curve.")

    c1, c2 = st.columns(2)
    with c1:
        head("Mean alignment trend", "soil")
        wk = soil.copy(); wk["week"] = wk.ts.dt.isocalendar().week
        wk = wk.groupby(["week", wk.plant_id.map(TREAT)]).pct.mean().unstack()
        f = go.Figure()
        for k in GROUPS:
            if k in wk:
                f.add_trace(go.Scatter(x=wk.index.astype(str), y=wk[k], mode="lines+markers",
                                       line=dict(color=CD[k], width=LW["growth"]), name=NAME[k].title()))
        f.update_layout(height=210, margin=dict(l=40, r=10, t=6, b=28),
                        legend=dict(orientation="h", y=1.14, font=dict(size=10, color=INK)), **BLANK)
        f.update_yaxes(gridcolor=RULE); f.update_xaxes(gridcolor=RULE)
        st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False}, key="align_trend")
    with c2:
        head("Midday droop — (dawn − pm) / dawn", "growth")
        if "phase" in grow and {"dawn", "pm"} <= set(grow.phase.unique()):
            g2 = grow.copy(); g2["day"] = g2.ts.dt.date
            pv = g2.pivot_table(index=["day", "plant_id"], columns="phase", values="area_px").dropna()
            pv["droop"] = 100 * (pv.dawn - pv.pm) / pv.dawn
            last = pv.reset_index().groupby("plant_id").last().reset_index()
            # 처짐은 같은 날 dawn·pm 이 <둘 다> 있어야 계산됩니다.
            # 한쪽이 없거나 ok=0 이면 그 화분은 여기 없습니다 -> .loc 로 찍으면 KeyError.
            have = [p for p in POTS if p in set(last.plant_id)]
            last = last.set_index("plant_id").loc[have].reset_index()      # 처리군 순서 유지
            missing = [p for p in POTS if p not in have]
            f = go.Figure(go.Bar(
                x=last.plant_id.str.upper(), y=last.droop,
                marker=dict(color=[CT[TREAT[p]] for p in last.plant_id],
                            line=dict(color=[CD[TREAT[p]] for p in last.plant_id], width=1.5)),
                text=last.droop.round(1), textposition="outside",
                textfont=dict(color=INK)))
            f.update_layout(height=210, margin=dict(l=40, r=10, t=6, b=28), showlegend=False,
                            yaxis_title="%", **BLANK)
            f.update_yaxes(gridcolor=RULE)
            if len(last):
                st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False}, key="droop")
            if missing:
                st.caption(f"{', '.join(p.upper() for p in missing)} — 같은 날 dawn·pm 이 "
                           f"모두 필요합니다 (한쪽이 없거나 ok=0)")
            if not len(last):
                st.caption("아직 dawn·pm 이 짝을 이룬 날이 없습니다.")
        else:
            st.caption("Needs both dawn and pm captures.")


# ═══════════════ GROWTH ═══════════════
with tab_gr:
    head("Canopy area — dawn series", "growth")
    dawn = grow[grow.phase == "dawn"] if "phase" in grow else grow
    if dawn.empty:
        st.caption("No dawn captures yet.")
    else:
        f = go.Figure()
        for p in POTS:
            d = dawn[dawn.plant_id == p]
            f.add_trace(go.Scatter(x=d.ts, y=d.area_cm2, mode="lines+markers", name=p.upper(),
                                   line=dict(color=CD[TREAT[p]], width=LW["growth"]),
                                   marker=dict(size=6)))
        f.update_layout(height=330, margin=dict(l=46, r=14, t=8, b=30), yaxis_title="cm²",
                        legend=dict(orientation="h", y=1.1, font=dict(size=10, color=INK)), **BLANK)
        f.update_yaxes(gridcolor=RULE); f.update_xaxes(gridcolor=RULE)
        st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False}, key="canopy_series")

        head("Relative growth rate — log-slope over all dawn frames", "growth")
        rows = []
        for p in POTS:
            d = dawn[dawn.plant_id == p].sort_values("ts").dropna(subset=["area_cm2"])
            d = d[d.area_cm2 > 0]
            if len(d) < 3:
                continue
            t = (d.ts - d.ts.iloc[0]).dt.total_seconds().to_numpy() / 86400
            y = np.log(d.area_cm2.to_numpy())
            # ln(면적) vs 일수의 최소제곱 기울기 = RGR. 끝점 하나에 휘둘리지 않음.
            slope, intercept = np.polyfit(t, y, 1)
            resid = y - (slope * t + intercept)
            se = float(np.sqrt((resid ** 2).sum() / (len(t) - 2) /
                               ((t - t.mean()) ** 2).sum())) if len(t) > 2 else np.nan
            r2 = 1 - (resid ** 2).sum() / ((y - y.mean()) ** 2).sum()
            rows.append(dict(pot=p, treat=TREAT[p], rgr=float(slope), se=se, r2=float(r2),
                             n=len(t)))
        r = pd.DataFrame(rows)

        if len(r) and r.treat.nunique() == 2:
            a, b = r[r.treat == "stable"].rgr, r[r.treat == "fluct"].rgr
            pooled = np.sqrt((a.std() ** 2 + b.std() ** 2) / 2)
            d_eff  = (a.mean() - b.mean()) / pooled if pooled else np.nan
            c = st.columns(3)
            c[0].metric("RGR Stable", f"{a.mean():.4f} /d",
                        f"sd {a.std():.4f} · n={len(a)}", delta_color="off")
            c[1].metric("RGR Fluctuating", f"{b.mean():.4f} /d",
                        f"sd {b.std():.4f} · n={len(b)}", delta_color="off")
            c[2].metric("Cohen's d", f"{d_eff:.2f}",
                        "large" if abs(d_eff) >= .8 else
                        "medium" if abs(d_eff) >= .5 else "small", delta_color="off")

            # 화분별 RGR ± 95% CI — 개체차와 그룹차를 눈으로 분리
            f = go.Figure()
            for k in GROUPS:
                sub = r[r.treat == k]
                f.add_trace(go.Scatter(
                    x=sub.rgr, y=sub.pot.str.upper(), mode="markers",
                    error_x=dict(type="data", array=1.96 * sub.se, color=CD[k], thickness=2),
                    marker=dict(size=12, color=CT[k], line=dict(color=CD[k], width=2)),
                    name=NAME[k].title()))
                f.add_vline(x=float(sub.rgr.mean()), line=dict(color=CD[k], width=1.6, dash="dot"))
            f.update_layout(height=190, margin=dict(l=46, r=16, t=6, b=34),
                            xaxis_title="RGR (/day)  — dotted line = group mean",
                            legend=dict(orientation="h", y=1.22, font=dict(size=10, color=INK)), **BLANK)
            f.update_xaxes(gridcolor=RULE); f.update_yaxes(gridcolor=RULE)
            st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False}, key="rgr_ci")

            worst = r.r2.min()
            st.caption(
                f"Slope of ln(area) vs day, least squares over all dawn frames "
                f"(worst fit R²={worst:.3f}). "
                f"With n=3, p>0.05 is **not** 'no effect' — report the effect size. "
                f"Projected area saturates as leaves overlap, so the week-6 harvest "
                f"(true leaf area, dry mass, roots) is the arbiter.")
        elif len(r):
            st.caption("Only one treatment group so far — no comparison yet.")

with st.expander("Export CSV"):
    for nm, df in [("readings", env), ("soil", soil), ("pump_log", pump), ("growth", grow)]:
        st.download_button(nm + (" (demo)" if nm.split("_")[0] in FAKE else ""),
                           df.to_csv(index=False), f"{nm}.csv", "text/csv", key=nm)
