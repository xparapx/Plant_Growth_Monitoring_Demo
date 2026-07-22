"""Read-only view over plant.db.  Runs unchanged on PC or Pi."""
import sqlite3
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

DB = "plant.db"
st.set_page_config(page_title="식물 생장 모니터", layout="wide")
st_autorefresh(interval=60_000, key="tick")

@st.cache_data(ttl=30)
def q(sql):
    with sqlite3.connect(DB) as c:
        df = pd.read_sql_query(sql, c)
    if "ts" in df and not df.empty:
        df["ts"] = pd.to_datetime(df["ts"]) + pd.Timedelta(hours=9)   # UTC -> KST
    return df

st.title("🌱 식물 생장 모니터링")

# ── 환경 (재배함 공통) ──
env = q("SELECT * FROM readings ORDER BY id DESC LIMIT 288")
if env.empty:
    st.warning("환경 데이터 없음 — 환경 노드와 hub.py 확인")
else:
    cur = env.iloc[0]
    c = st.columns(5)
    c[0].metric("온도", f"{cur.temp:.1f} °C")
    c[1].metric("습도", f"{cur.hum:.0f} %")
    c[2].metric("조도", f"{cur.lux:,.0f} lx")
    c[3].metric("VPD",  f"{cur.vpd:.2f} kPa", help="증산 = 마르는 속도를 정하는 값")
    c[4].metric("CO₂",  f"{cur.co2:.0f} ppm")
    e = env.sort_values("ts")
    fig = go.Figure()
    for col, name in [("temp", "온도 °C"), ("vpd", "VPD kPa"), ("co2", "CO₂ ppm")]:
        fig.add_trace(go.Scatter(x=e.ts, y=e[col], name=name,
                                 yaxis="y2" if col == "co2" else "y"))
    fig.update_layout(height=280, yaxis2=dict(overlaying="y", side="right"),
                      margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

# ── 토양수분 + 급수 (화분별) ──
st.subheader("토양수분 · 급수")
so = q("SELECT * FROM soil ORDER BY ts")
if so.empty:
    st.info("토양 데이터 없음 — 급수 노드 확인")
else:
    f = px.line(so, x="ts", y="pct", color="plant_id", line_dash="treat",
                labels={"pct": "수분 (%)", "ts": ""})
    pl = q("SELECT * FROM pump_log ORDER BY ts")
    if not pl.empty:
        f.add_trace(go.Scatter(x=pl.ts, y=pl.soil_after, mode="markers",
                               name="급수", marker=dict(size=11, symbol="triangle-up")))
    f.update_layout(height=320)
    st.plotly_chart(f, use_container_width=True)

    bad = q("SELECT * FROM pump_log WHERE reason='verify_fail'")
    if not bad.empty:
        st.error(f"⚠️ 급수 검증 실패 {len(bad)}건 — 튜브·물통·펌프 점검 후 노드 재시작")

# ── 성장 ──
st.subheader("성장 — 투영 캐노피 면적")
g = q("SELECT * FROM growth WHERE ok=1 ORDER BY ts")
if g.empty:
    st.info("성장 데이터 없음 — grow_node.py 실행")
else:
    st.plotly_chart(px.line(g, x="ts", y="area_cm2", color="plant_id",
                            line_dash="treat", markers=True,
                            labels={"area_cm2": "면적 (cm²)", "ts": ""}),
                    use_container_width=True)
    # RGR = (ln A2 - ln A1)/dt  -- 큰 개체가 절대량으로 더 자라므로 원면적 비교는 부당
    g["day"] = g.ts.dt.date
    d = g.groupby(["day", "plant_id", "treat"], as_index=False)["area_cm2"].mean()
    d = d.sort_values(["plant_id", "day"])
    d["rgr"] = d.groupby("plant_id")["area_cm2"].transform(
        lambda s: np.log(s.clip(lower=0.1)).diff())
    r = d.dropna(subset=["rgr"])
    if not r.empty:
        st.caption("RGR = (ln A₂ − ln A₁) / Δt · 개체 크기와 무관하게 '자라는 속도'를 비교")
        st.plotly_chart(px.box(r, x="treat", y="rgr", color="treat", points="all",
                               labels={"rgr": "RGR (day⁻¹)"}),
                        use_container_width=True)

with st.expander("CSV 내보내기"):
    for name, sql in [("환경", "SELECT * FROM readings"), ("토양", "SELECT * FROM soil"),
                      ("급수", "SELECT * FROM pump_log"), ("성장", "SELECT * FROM growth")]:
        df = q(sql)
        st.download_button(f"{name} 내려받기", df.to_csv(index=False), f"{name}.csv", "text/csv")
