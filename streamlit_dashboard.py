import json
from math import sqrt
from datetime import datetime
from dateutil import tz
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------
# 페이지 설정 & 임베디드 CSS (브랜드 스타일)
# ---------------------------
st.set_page_config(page_title="SNS 공유 인사이트 (행동 시퀀스)", layout="wide", page_icon="📈")

BRAND_CSS = """
:root{
  --accent:#00A6A6; --danger:#FF6B6B; --ink:#1F2937; --muted:#6B7280; --bg:#FAFAFA;
}
html, body { background: var(--bg); }
.block-title { font-size:18px; font-weight:800; margin:4px 0 12px; color:var(--ink); }
.kpi { font-size:42px; font-weight:900; color:var(--accent); line-height:1; }
.kpi-sub { color:var(--muted); font-size:13px; }
.badge { display:inline-block; padding:6px 10px; border-radius:999px; font-size:12px; font-weight:700; letter-spacing:.2px; margin-right:8px; }
.badge-danger { background:#FFE4E1; color:var(--danger); border:1px solid #FFC4BE; }
.badge-ok { background:#DFF5F5; color:var(--accent); border:1px solid #BFECEC; }
.card { border:1px solid #eaeaea; border-radius:16px; padding:18px; background:#fff; box-shadow:0 2px 18px rgba(0,0,0,.04); }
.small { font-size:12px; color:var(--muted); }
hr.soft { border:none; height:1px; background:#efefef; margin:12px 0; }
"""
st.markdown(f"<style>{BRAND_CSS}</style>", unsafe_allow_html=True)

# ---------------------------
# 유틸
# ---------------------------
def wilson_ci(success:int, total:int, z:float=1.96):
    """Binomial proportion 95% CI (Wilson)."""
    if total <= 0:
        return (0.0, 0.0)
    p = success / total
    denom = 1 + (z**2)/total
    center = (p + (z**2)/(2*total)) / denom
    margin = (z/denom) * sqrt((p*(1-p)/total) + (z**2)/(4*total**2))
    return (max(0.0, center - margin), min(1.0, center + margin))

@st.cache_data(show_spinner=False)
def parse_mixpanel_csv(file) -> pd.DataFrame:
    """(event, distinct_id, time, properties_json) CSV → 확장/정규화 + dwell_sec 계산"""
    df = pd.read_csv(file)
    # properties_json 파싱
    props = df["properties_json"].apply(lambda x: json.loads(x) if isinstance(x,str) else {})
    props_df = pd.json_normalize(props)
    out = pd.concat([df[["event","distinct_id","time"]], props_df], axis=1)
    out = out.loc[:, ~out.columns.duplicated()]  # 중복 컬럼 제거
    # 타임스탬프
    out["ts"] = pd.to_datetime(pd.to_numeric(out["time"], errors="coerce"), unit="s", errors="coerce", utc=True)
    # 정렬
    out = out.sort_values(["distinct_id","ts"]) 
    # 다음 이벤트 시각
    out["next_ts"] = out.groupby("distinct_id")["ts"].shift(-1)
    # dwell(추정): 다음 이벤트까지의 간격을 0~600초로 클립
    out["dwell_sec"] = (out["next_ts"] - out["ts"]).dt.total_seconds().clip(lower=0, upper=600)
    # sns_type 정규화
    out["sns_type"] = out.get("sns_type", "unknown")
    out["sns_type"] = out["sns_type"].fillna("unknown").astype(str).str.strip().str.lower()
    # 디바이스/브라우저/OS(있으면)
    for c in ["$device", "$browser", "$os"]:
        if c in out.columns:
            out[c] = out[c].astype(str)
    return out

# ---------------------------
# 입력: 기본 CSV 자동 로드 (+선택적 업로드)
# ---------------------------
st.markdown("## 인증서 상세페이지 · SNS 공유 인사이트 (행동 시퀀스 초점)")
st.caption("CSV 스키마 예: event, distinct_id, time, properties_json (Mixpanel Export)")

DEFAULT_PATH = Path("/mnt/data/mixpanel_raw.csv")  # 첨부된 기본 CSV 경로

def _try_load_default():
    if DEFAULT_PATH.exists():
        try:
            return parse_mixpanel_csv(DEFAULT_PATH)
        except Exception as e:
            st.warning(f"기본 CSV 로드 실패: {e}")
    return None

# 데이터 소스 선택(자동)
_autoload_df = _try_load_default()
show_uploader = st.toggle("수동 업로드 사용", value=False if _autoload_df is not None else True, help="기본 CSV가 있을 경우 자동 로드를 사용합니다.")

if not show_uploader and _autoload_df is not None:
    st.success(f"기본 CSV 자동 로드 완료 · 경로: {DEFAULT_PATH}")
    df = _autoload_df
else:
    uploaded = st.file_uploader("mixpanel_raw.csv 업로드", type=["csv"]) 
    if not uploaded:
        st.info("기본 CSV가 없거나 업로드를 선택하셨습니다. 파일을 업로드하면 대시보드가 생성됩니다.")
        st.stop()
    df = parse_mixpanel_csv(uploaded)

# ---------------------------
# 사이드바 필터
# ---------------------------
st.sidebar.markdown("### 필터")
min_ts, max_ts = df["ts"].min(), df["ts"].max()
start, end = st.sidebar.date_input(
    "기간",
    value=(min_ts.date() if pd.notna(min_ts) else None,
           max_ts.date() if pd.notna(max_ts) else None)
)
platforms = sorted(df["sns_type"].dropna().unique().tolist())
sel_platforms = st.sidebar.multiselect("sns_type", platforms, default=platforms)

extra_filters = {}
if "$device" in df.columns:
    devices = sorted(df["$device"].dropna().unique().tolist())[:50]
    extra_filters["$device"] = st.sidebar.multiselect("Device (선택적)", devices, default=devices)
if "$browser" in df.columns:
    browsers = sorted(df["$browser"].dropna().unique().tolist())[:50]
    extra_filters["$browser"] = st.sidebar.multiselect("Browser (선택적)", browsers, default=browsers)

mask = (df["ts"].dt.date >= pd.to_datetime(start).date()) & (df["ts"].dt.date <= pd.to_datetime(end).date())
mask &= df["sns_type"].isin(sel_platforms)
for c, vals in extra_filters.items():
    if c in df.columns and len(vals) > 0:
        mask &= df[c].isin(vals)
f = df[mask].copy()

# ---------------------------
# KPI & 병목
# ---------------------------
count_view  = (f["event"]=="Achievement Page View").sum()
count_open  = (f["event"]=="Open SNS Share Popup").sum()
count_share = (f["event"]=="Actual SNS Share").sum()

ctr  = (count_open / count_view) if count_view else 0
cvr  = (count_share / count_open) if count_open else 0
conv = (count_share / count_view) if count_view else 0

drop_v2o = max(0, count_view - count_open)
drop_o2s = max(0, count_open - count_share)
bottleneck = "View → Open" if drop_v2o >= drop_o2s else "Open → Share"
bottleneck_count = max(drop_v2o, drop_o2s)

# 헤더/KPI/배지
now_kr = datetime.now(tz.gettz("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S %Z")
left, right = st.columns([3,2])
with left:
    st.markdown(f"<span class='small'>KST {now_kr}</span>", unsafe_allow_html=True)
    st.markdown("<hr class='soft'/>", unsafe_allow_html=True)
    st.markdown("<div class='block-title'>핵심 KPI</div>", unsafe_allow_html=True)
    a,b,c = st.columns([1.2,1,1])
    with a:
        st.markdown(f"<div class='kpi'>{conv:.1%}</div>", unsafe_allow_html=True)
        st.markdown("<div class='kpi-sub'>Share Conversion (Share / View)</div>", unsafe_allow_html=True)
    with b:
        st.metric("Share CTR (Open / View)", f"{ctr:.1%}")
    with c:
        st.metric("Completion Rate (Share / Open)", f"{cvr:.1%}")
with right:
    st.markdown("<div class='block-title'>상태</div>", unsafe_allow_html=True)
    if bottleneck_count > 0:
        st.markdown(f"<span class='badge badge-danger'>🚨 Bottleneck: {bottleneck}</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span class='badge badge-ok'>✅ Bottleneck 없음</span>", unsafe_allow_html=True)
    st.caption("병목 단계에 '공유하면 어떤 효과?' 메시지/노출 타이밍 A/B 테스트 권장.")

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)

# ---------------------------
# 1) Sankey: 행동 시퀀스 흐름 (대형)
# ---------------------------
st.markdown("<div class='block-title'>1) 행동 시퀀스 (Sankey)</div>", unsafe_allow_html=True)
SEQ = ["Achievement Page View","Certificate Select Click","Certificate Download",
       "Open SNS Share Popup","Actual SNS Share"]
seq_df = f[f["event"].isin(SEQ)].sort_values(["distinct_id","ts"])
pairs = []
for uid, g in seq_df.groupby("distinct_id"):
    evs = g["event"].tolist()
    for a, b in zip(evs[:-1], evs[1:]):
        if a != b:
            pairs.append((a,b))
link_df = (pd.DataFrame(pairs, columns=["src","dst"]).value_counts()
           .reset_index(name="value")) if pairs else pd.DataFrame(columns=["src","dst","value"])
labels = sorted(set(link_df["src"]).union(set(link_df["dst"]))) if len(link_df) else SEQ
idx = {lab:i for i,lab in enumerate(labels)}
fig_sankey = go.Figure(data=[go.Sankey(
    node=dict(label=labels,
              color=["#A6CEE3","#B2DF8A","#FDBF6F","#FB9A99","#CAB2D6"],
              pad=16, thickness=16),
    link=dict(source=[idx[s] for s in link_df["src"]] if len(link_df) else [],
              target=[idx[t] for t in link_df["dst"]] if len(link_df) else [],
              value=link_df["value"] if len(link_df) else [],
              color="rgba(0,166,166,0.30)")
)])
fig_sankey.update_layout(margin=dict(l=10,r=10,t=10,b=10), height=420)
st.plotly_chart(fig_sankey, use_container_width=True)
st.caption("굵을수록 많이 발생한 경로. 노드/링크 hover로 전환 수 확인, 시나리오별 병목 파악.")

# ---------------------------
# 2) 체류시간: Sharers vs Non-sharers (바이올린+스트립)
# ---------------------------
st.markdown("<div class='block-title'>2) 체류시간(추정) 분포: Sharers vs Non-sharers</div>", unsafe_allow_html=True)
sharer_ids = set(f.loc[f["event"]=="Actual SNS Share","distinct_id"].unique().tolist())
pv = f[f["event"]=="Achievement Page View"]["distinct_id"].to_frame().join(
    f[f["event"]=="Achievement Page View"]["dwell_sec"].reset_index(drop=True)
)
pv["group"] = pv["distinct_id"].apply(lambda x: "Sharers" if x in sharer_ids else "Non-sharers")
fig_violin = px.violin(pv, x="group", y="dwell_sec", box=True, points="all",
                       color="group", color_discrete_sequence=["#00A6A6","#9CA3AF"])
fig_violin.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10))
fig_violin.update_yaxes(title="Estimated Dwell Time on Page (sec)")
st.plotly_chart(fig_violin, use_container_width=True)
st.caption("원본 duration_seconds가 없어, 다음 이벤트까지의 시간차(0~600초)를 체류시간 추정치로 사용.")

# ---------------------------
# 3) 플랫폼 효율 보드 (정규화 + 95% CI)
# ---------------------------
st.markdown("<div class='block-title'>3) 플랫폼 효율 보드 (정규화 + 신뢰구간)</div>", unsafe_allow_html=True)
sub = f[f["event"].isin(["Open SNS Share Popup","Actual SNS Share"])].copy()
sub["event_stage"] = sub["event"].map({"Open SNS Share Popup":"popup","Actual SNS Share":"complete"})

# 분포(정규화)
dist = (sub.groupby(["event_stage","sns_type"]).size()
          .groupby(level=0).apply(lambda s: 100*s/s.sum()).reset_index(name="pct"))
fig_dist = px.bar(dist, x="sns_type", y="pct", color="event_stage",
                  barmode="group", color_discrete_sequence=["#6EE7E7","#00A6A6"],
                  labels={"pct":"비중(%)","sns_type":"플랫폼","event_stage":"단계"})
fig_dist.update_layout(height=340, margin=dict(l=10,r=10,t=10,b=10))
st.plotly_chart(fig_dist, use_container_width=True)

# CVR + Wilson CI
open_by = sub[sub["event_stage"]=="popup"]["sns_type"].value_counts()
comp_by = sub[sub["event_stage"]=="complete"]["sns_type"].value_counts()
plats = sorted(set(open_by.index).union(set(comp_by.index)))
rows=[]
for p_name in plats:
    o = int(open_by.get(p_name,0)); c = int(comp_by.get(p_name,0))
    _cvr = c/o if o>0 else 0.0
    lo, hi = wilson_ci(c, o) if o>0 else (0.0,0.0)
    rows.append({"sns_type":p_name,"open":o,"complete":c,"CVR":_cvr,"CI_low":lo,"CI_high":hi})
cvr_df = pd.DataFrame(rows).sort_values("CVR", ascending=False)

fig_cvr = go.Figure()
fig_cvr.add_trace(go.Bar(
    x=cvr_df["sns_type"], y=cvr_df["CVR"], name="Completion Rate", marker_color="#00A6A6",
    hovertemplate="플랫폼=%{x}<br>CVR=%{y:.1%}<br>Open=%{customdata[0]} / Complete=%{customdata[1]}<extra></extra>",
    customdata=cvr_df[["open","complete"]].values
))
fig_cvr.add_trace(go.Scatter(x=cvr_df["sns_type"], y=cvr_df["CI_high"], mode="lines",
                             line=dict(width=0), showlegend=False, hoverinfo="skip"))
fig_cvr.add_trace(go.Scatter(x=cvr_df["sns_type"], y=cvr_df["CI_low"], mode="lines", fill="tonexty",
                             line=dict(width=0), fillcolor="rgba(0,166,166,0.15)", name="95% CI", hoverinfo="skip"))
fig_cvr.update_yaxes(tickformat=".0%")
fig_cvr.update_layout(height=360, margin=dict(l=10,r=10,t=10,b=10))
st.plotly_chart(fig_cvr, use_container_width=True)

# 인사이트 배지
if len(cvr_df) > 0:
    top = cvr_df.iloc[0]; low = cvr_df.iloc[-1]
    st.markdown(
        f"<span class='badge badge-ok'>👍 High CVR: {top['sns_type']} ({top['CVR']:.1%})</span> "
        f"<span class='badge badge-danger'>⚠️ Low CVR: {low['sns_type']} ({low['CVR']:.1%})</span>",
        unsafe_allow_html=True
    )
    st.caption("플랫폼별 '시도(팝업)→완료' 효율을 정규화하여 비교. CI는 샘플 수 불확실성 반영.")

st.markdown("<hr class='soft'/>", unsafe_allow_html=True)
st.markdown("**Tip**: Sankey 링크가 굵은 경로에 메시지/노출 타이밍 실험을 배치하고, CVR 상위 플랫폼에 리소스를 집중하세요.")
