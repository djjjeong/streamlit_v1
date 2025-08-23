
import pandas as pd
import numpy as np
import streamlit as st
import pytz

st.set_page_config(page_title="SVG Tooltip Dashboard (Streamlit)", layout="wide")
st.title("Share Insights — SVG + Vanilla JS Tooltips")
st.caption("정적 CSV를 한 번 읽어, 인라인 SVG 차트에 바닐라 JS 툴팁을 제공합니다. 자동갱신/폴링 없음.")

# ---- Sidebar: Controls ----
st.sidebar.header("설정")
session_timeout_min = st.sidebar.number_input("세션 타임아웃 (분)", min_value=5, max_value=240, value=30, step=5)
funnel_window_days = st.sidebar.number_input("퍼널 윈도우 (일)", min_value=1, max_value=14, value=1, step=1)

st.sidebar.markdown("**CSV 업로드** (필수 컬럼: `distinct_id,event,time`)")
file = st.sidebar.file_uploader("mixpanel_raw.csv 선택", type=["csv"])
if file is None:
    st.info("좌측에서 CSV를 업로드하세요.")
    st.stop()

# ---- Load ----
try:
    df = pd.read_csv(file)
except Exception as e:
    st.error(f"CSV 읽기 실패: {e}")
    st.stop()

# ---- Basic validation ----
required_cols = {"distinct_id", "event", "time"}
missing = required_cols - set(df.columns)
if missing:
    st.error(f"필수 컬럼 누락: {missing}. 최소 {required_cols} 가 필요합니다.")
    st.stop()

# ---- Robust time parser (epoch s/ms/ns OR ISO strings -> KST) ----
def parse_to_kst(series: pd.Series) -> pd.Series:
    s = series.copy()
    # prefer numeric path if majority numeric
    s_num = pd.to_numeric(s, errors="coerce")
    numeric_ratio = s_num.notna().mean()
    if numeric_ratio >= 0.8:
        maxv = s_num.max()
        if maxv > 1e14:
            unit = "ns"
        elif maxv > 1e12:
            unit = "ms"
        else:
            unit = "s"
        dt = pd.to_datetime(s_num, unit=unit, utc=True, errors="coerce")
    else:
        dt = pd.to_datetime(s, utc=True, errors="coerce", infer_datetime_format=True)
    return dt.dt.tz_convert("Asia/Seoul")

df["time"] = parse_to_kst(df["time"])
before = len(df)
df = df.dropna(subset=["time"])
dropped = before - len(df)
if dropped:
    st.warning(f"시간 파싱 실패로 {dropped}행이 제외되었습니다.")

# ---- Deduplicate (distinct_id + event + time±5s) ----
df["_time5"] = df["time"].dt.floor("5s")
df = df.sort_values(["distinct_id", "event", "_time5"]).drop_duplicates(["distinct_id", "event", "_time5"], keep="first")

# ---- Event pickers (from data) ----
all_events = df["event"].dropna().astype(str).unique().tolist()
# naive defaults
default_entry = next((e for e in all_events if "Select" in e or "View" in e or "Detail" in e), all_events[0] if all_events else "")
default_final = next((e for e in all_events if "Share" in e or "Download" in e), all_events[min(1, len(all_events)-1)] if len(all_events)>1 else default_entry)

st.sidebar.markdown("**퍼널 이벤트 선택**")
entry_event = st.sidebar.selectbox("진입 이벤트", options=all_events, index=max(all_events.index(default_entry),0) if all_events else 0, key="entry")
final_event = st.sidebar.selectbox("최종 이벤트", options=all_events, index=max(all_events.index(default_final),0) if all_events else 0, key="final")

st.write(f"선택된 퍼널: **{entry_event} → {final_event}**")

# ---- Sessionization (gap > timeout -> new session) ----
df = df.sort_values(["distinct_id", "time"])
gap = df.groupby("distinct_id")["time"].diff().dt.total_seconds().div(60).fillna(1e9)
session_break = gap.gt(session_timeout_min).astype(int)
df["_session_id"] = (session_break.groupby(df["distinct_id"]).cumsum()).astype(int)

# ---- Funnel conversion (within window & same session) ----
window = pd.Timedelta(days=int(funnel_window_days))

def session_conv(group: pd.DataFrame) -> pd.DataFrame:
    g = group.sort_values("time")
    entries = g[g["event"] == entry_event]["time"]
    finals  = g[g["event"] == final_event]["time"]
    if entries.empty:
        return pd.DataFrame(columns=["entry_time", "converted"])
    if finals.empty:
        return pd.DataFrame({"entry_time": entries, "converted": False})
    f_list = finals.tolist()
    res = []
    for et in entries:
        ok = any((ft >= et) and ((ft - et) <= window) for ft in f_list)
        res.append({"entry_time": et, "converted": ok})
    return pd.DataFrame(res)

conv_list = []
for (uid, sid), g in df.groupby(["distinct_id", "_session_id"]):
    out = session_conv(g)
    if not out.empty:
        out["distinct_id"] = uid
        out["_session_id"] = sid
        conv_list.append(out)
conv_df = pd.concat(conv_list, ignore_index=True) if conv_list else pd.DataFrame(columns=["entry_time","converted","distinct_id","_session_id"])

if conv_df.empty:
    st.error("퍼널 계산 결과가 비어 있습니다. 선택한 이벤트 조합으로 최종 전환이 윈도우 내에 발생하지 않았습니다.")
    st.stop()

# ---- Weekly aggregation (KST, week starts Monday) ----
conv_df["week"] = conv_df["entry_time"].dt.to_period("W-MON").dt.start_time
weekly = conv_df.groupby("week").agg(
    entries=("converted","size"),
    conversions=("converted","sum")
).reset_index()
weekly["conversion_rate"] = (weekly["conversions"] / weekly["entries"] * 100).round(2)

# ---- Build SVG data ----
W, H = 800, 400
ML, MR, MT, MB = 50, 40, 30, 40
plot_w, plot_h = W - ML - MR, H - MT - MB

x_vals = weekly["week"].sort_values().tolist()
y_vals = weekly.set_index("week").loc[x_vals, "conversion_rate"].values.astype(float) if len(weekly) else np.array([])

x_min, x_max = 0, max(1, len(x_vals)-1)
y_min = float(min(0.0, float(np.nanmin(y_vals)) if len(y_vals) else 0.0))
y_max = float(max(5.0, float(np.nanmax(y_vals)) if len(y_vals) else 5.0))
y_pad = (y_max - y_min) * 0.1 if y_max > y_min else 1.0
y_min, y_max = y_min, y_max + y_pad

def x_scale(i: int) -> float:
    if x_max == x_min: 
        return ML + plot_w/2
    return ML + (i - x_min) * (plot_w / (x_max - x_min))

def y_scale(v: float) -> float:
    if y_max == y_min: 
        return MT + plot_h/2
    return MT + (y_max - v) * (plot_h / (y_max - y_min))

points = [(x_scale(i), y_scale(v)) for i, v in enumerate(y_vals)]
path_d = " ".join([("M" if i==0 else "L") + f" {x:.2f} {y:.2f}" for i,(x,y) in enumerate(points)]) if points else ""

x_labels = [pd.Timestamp(w).tz_localize("Asia/Seoul") for w in x_vals]
x_texts = [ts.strftime("%m-%d") for ts in x_labels]
grid_y_vals = np.linspace(y_min, y_max, 5)

# Compose small HTML snippets first
circles_html = ""
for i, (x, y) in enumerate(points):
    label = x_texts[i]
    val = f"{y_vals[i]:.2f}%"
    circles_html += f'<circle class="dot" cx="{x:.2f}" cy="{y:.2f}" r="5" tabindex="0" data-x="{label}" data-y="{val}" aria-describedby="t2"></circle>\\n        '

xticks_html = ""
for i, x in enumerate([p[0] for p in points]):
    xticks_html += f'<text x="{x:.2f}" y="{H - MB + 18}" font-size="12" text-anchor="middle" fill="currentColor" opacity="0.7">{x_texts[i]}</text>\\n        '

ygrid_html = ""
for gy in grid_y_vals:
    yy = y_scale(float(gy))
    ygrid_html += f'<path d="M {ML} {yy:.2f} H {W - MR}" stroke="currentColor" opacity="0.15"></path>\\n        '
    ygrid_html += f'<text x="{ML - 8}" y="{yy + 4:.2f}" font-size="12" text-anchor="end" fill="currentColor" opacity="0.7">{gy:.1f}%</text>\\n        '

template = '''
<style>
  .chart-wrap{position:relative}
  .tooltip2{position:absolute;display:none;pointer-events:none;background:#111315;color:#eee;border:1px solid #22262a;border-radius:10px;padding:6px 8px;font-size:12px;box-shadow:0 6px 24px rgba(0,0,0,.2)}
  .tooltip2.show{display:block}
  .dot{cursor:pointer} .dot:focus{outline:2px solid #93c5fd; outline-offset:2px}
</style>
<div class="chart-wrap" aria-label="주간 전환율 추이">
  <svg id="convSvg" viewBox="0 0 __W__ __H__" width="100%" height="auto" role="img" aria-labelledby="ttl">
    <title id="ttl">주간 전환율 추이 (단위: %)</title>
    <g stroke="currentColor">
      __YGRID__
    </g>
    <path d="M __ML__ __XLINE_Y__ H __XR__" stroke="currentColor" opacity="0.4"></path>
    <g>
      __XTICKS__
    </g>
    <path d="__PATH_D__" fill="none" stroke="#1f77b4" stroke-width="2.5"></path>
    <g fill="#1f77b4" id="convDots">
      __CIRCLES__
    </g>
  </svg>
  <div id="t2" class="tooltip2" role="tooltip" aria-hidden="true"></div>
</div>
<script>
  (function(){
    const wrap = document.currentScript.previousElementSibling;
    const tip  = wrap.querySelector('#t2');
    function showTip(evt){
      const el = evt.currentTarget;
      const rect = wrap.getBoundingClientRect();
      const bbox = el.getBoundingClientRect();
      const x = evt.clientX !== undefined ? evt.clientX : (bbox.left + bbox.width/2);
      const y = evt.clientY !== undefined ? evt.clientY : (bbox.top);
      tip.innerHTML = "<strong>" + el.dataset.x + "</strong><br/>전환율 " + el.dataset.y;
      tip.style.left = (x - rect.left + 12) + "px";
      tip.style.top  = (y - rect.top  - 36) + "px";
      tip.classList.add("show"); tip.setAttribute("aria-hidden","false");
    }
    function hideTip(){
      tip.classList.remove("show"); tip.setAttribute("aria-hidden","true");
    }
    wrap.querySelectorAll('#convDots .dot').forEach(dot=>{
      dot.addEventListener('mouseenter', showTip);
      dot.addEventListener('mousemove', showTip);
      dot.addEventListener('mouseleave', hideTip);
      dot.addEventListener('focus', (e)=>showTip(e));
      dot.addEventListener('blur', hideTip);
      dot.addEventListener('keydown', (e)=>{ if(e.key==='Escape') hideTip(); });
    });
  })();
</script>
'''

html = (
    template
    .replace("__W__", str(800))
    .replace("__H__", str(400))
    .replace("__ML__", str(50))
    .replace("__XR__", str(800 - 40))
    .replace("__XLINE_Y__", str(400 - 40))
    .replace("__YGRID__", ygrid_html)
    .replace("__XTICKS__", xticks_html)
    .replace("__PATH_D__", path_d)
    .replace("__CIRCLES__", circles_html)
)

st.subheader("퍼널 전환 추이 (주간, SVG 인터랙션)")
st.components.v1.html(html, height=460, scrolling=False)

col1, col2 = st.columns([2,1])
with col1:
    st.markdown("**주간 전환 테이블**")
    st.dataframe(weekly.rename(columns={
        "week":"주차(월 시작)",
        "entries":"진입 수",
        "conversions":"전환 수",
        "conversion_rate":"전환율(%)"
    }))
with col2:
    st.markdown("**설명**")
    st.write(f"- 타임존: KST\n- 세션 타임아웃: {session_timeout_min}분\n- 퍼널 윈도우: {funnel_window_days}일")
    if len(weekly):
        last = weekly.iloc[-1]
        st.metric(label="최근 주 전환율", value=f"{last['conversion_rate']:.2f}%")
