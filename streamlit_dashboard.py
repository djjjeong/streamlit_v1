import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="엑셀 시트별 대시보드", layout="wide")

# -----------------------------
# 공통 유틸
# -----------------------------
def moving_average(data, window_size):
    out = []
    for i in range(len(data)):
        if i < window_size - 1:
            out.append(None)
        else:
            out.append(sum(data[i - window_size + 1:i + 1]) / window_size)
    return out

# -----------------------------
# 바차트_히스토그램 대시보드
# -----------------------------
def show_bar_histogram_dashboard():
    labels = ["2023-01", "2023-02", "2023-03", "2023-04", "2023-05", "2023-06", "2023-07", "2023-08", "2023-09", "2023-10", "2023-11", "2023-12"]
    sales = [885, 918, 887, 1148, 1436, 1205, 1322, 1287, 1398, 1510, 1450, 1600]

    pct_change = [0] + [round((sales[i] - sales[i-1]) / sales[i-1] * 100, 1) for i in range(1, len(sales))]
    ma3 = moving_average(sales, 3)

    st.subheader("① 세로 막대형 바차트")
    colors = ["gray"] + ["steelblue" if sales[i] >= sales[i-1] else "tomato" for i in range(1, len(sales))]
    fig_bar = go.Figure([go.Bar(x=labels, y=sales, marker_color=colors)])
    fig_bar.update_layout(xaxis_title="월", yaxis_title="총 매출")
    st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("② 꺾은선+막대 혼합 차트")
    fig_combo = go.Figure()
    fig_combo.add_trace(go.Bar(x=labels, y=sales, name="총 매출", marker_color="lightblue", yaxis="y"))
    fig_combo.add_trace(go.Scatter(x=labels, y=pct_change, name="전월 대비 % 변화", mode="lines+markers", marker_color="orange", yaxis="y2"))
    fig_combo.update_layout(yaxis=dict(title="총 매출"), yaxis2=dict(title="% 변화", overlaying="y", side="right"))
    st.plotly_chart(fig_combo, use_container_width=True)

    st.subheader("③ 이동평균선 시계열 그래프")
    fig_ma = go.Figure()
    fig_ma.add_trace(go.Scatter(x=labels, y=sales, mode="lines+markers", name="원본 매출"))
    fig_ma.add_trace(go.Scatter(x=labels, y=ma3, mode="lines+markers", name="3개월 이동평균"))
    fig_ma.update_layout(xaxis_title="월", yaxis_title="매출")
    st.plotly_chart(fig_ma, use_container_width=True)

    st.subheader("④ 히트맵 형태 차트")
    fig_heatmap = px.bar(x=labels, y=sales, color=sales, color_continuous_scale="Blues", labels={"x":"월","y":"매출","color":"매출"})
    st.plotly_chart(fig_heatmap, use_container_width=True)

# -----------------------------
# 시계열차트 대시보드
# -----------------------------
def show_timeseries_dashboard():
    labels = ["2023-01", "2023-02", "2023-03", "2023-04", "2023-05", "2023-06", "2023-07", "2023-08", "2023-09", "2023-10", "2023-11", "2023-12"]
    productA = [272, 147, 217, 292, 423, 301, 334, 390, 355, 410, 398, 450]
    productB = [86, 137, 120, 266, 138, 190, 178, 165, 200, 230, 210, 250]
    productC = [158, 407, 235, 95, 403, 310, 280, 320, 360, 390, 400, 420]
    productD = [222, 97, 167, 242, 373, 350, 330, 300, 310, 305, 320, 315]
    productE = [147, 130, 148, 253, 99, 180, 200, 220, 210, 215, 205, 225]

    st.subheader("① 멀티 시리즈 꺾은선 그래프")
    fig_multi = go.Figure()
    for name, data in zip(['제품 A','제품 B','제품 C','제품 D','제품 E'],
                          [productA, productB, productC, productD, productE]):
        fig_multi.add_trace(go.Scatter(x=labels, y=data, mode='lines+markers', name=name))
    st.plotly_chart(fig_multi, use_container_width=True)

    st.subheader("② 누적 영역 차트")
    fig_stack = go.Figure()
    for name, data in zip(['제품 A','제품 B','제품 C','제품 D','제품 E'],
                          [productA, productB, productC, productD, productE]):
        fig_stack.add_trace(go.Scatter(x=labels, y=data, stackgroup='one', name=name))
    st.plotly_chart(fig_stack, use_container_width=True)

    st.subheader("③ 전월 대비 증감률 라인 차트")
    def pct_change(arr):
        return [0] + [round((arr[i] - arr[i-1]) / arr[i-1] * 100, 1) for i in range(1, len(arr))]
    fig_growth = go.Figure()
    for name, data in zip(['제품 A','제품 B','제품 C','제품 D','제품 E'],
                          [productA, productB, productC, productD, productE]):
        fig_growth.add_trace(go.Scatter(x=labels, y=pct_change(data), mode='lines+markers', name=name))
    fig_growth.update_layout(yaxis_title="% 변화")
    st.plotly_chart(fig_growth, use_container_width=True)

    st.subheader("④ Small Multiples (제품별 추세)")
    cols = st.columns(2)
    items = [('제품 A', productA), ('제품 B', productB), ('제품 C', productC), ('제품 D', productD), ('제품 E', productE)]
    for i, (name, data) in enumerate(items):
        with cols[i % 2]:
            fig_small = go.Figure()
            fig_small.add_trace(go.Scatter(x=labels, y=data, mode='lines+markers', name=name))
            fig_small.update_layout(title=f"{name} 추세")
            st.plotly_chart(fig_small, use_container_width=True)

# -----------------------------
# 파이차트 대시보드
# -----------------------------
def show_piechart_dashboard():
    labels = ['제품 A', '제품 B', '제품 C', '제품 D', '제품 E']
    sales = [3595, 2018, 3353, 2928, 2073]
    colors = ['#ff6b6b','#4dabf7','#51cf66','#fcc419','#845ef7']
    total_sales = sum(sales)

    st.subheader("① 기본 파이 차트")
    fig_pie = px.pie(names=labels, values=sales, color=labels, color_discrete_sequence=colors, hole=0)
    fig_pie.update_traces(textinfo='percent+label')
    st.plotly_chart(fig_pie, use_container_width=True)

    st.subheader("② 도넛 차트 (총 매출 표시)")
    fig_donut = px.pie(names=labels, values=sales, color=labels, color_discrete_sequence=colors, hole=0.6)
    fig_donut.update_traces(textinfo='percent+label', hovertemplate='%{label}: %{value} (%{percent})')
    fig_donut.update_layout(title=f"총 매출: {total_sales:,}")
    st.plotly_chart(fig_donut, use_container_width=True)

    st.subheader("③ 누적 기여도 바 차트")
    sorted_data = sorted(zip(labels, sales, colors), key=lambda x: x[1], reverse=True)
    fig_bar = go.Figure([go.Bar(x=[x[0] for x in sorted_data], y=[x[1] for x in sorted_data], marker_color=[x[2] for x in sorted_data])])
    fig_bar.update_layout(yaxis_title="매출")
    st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("④ 트리맵")
    fig_treemap = px.treemap(names=labels, parents=["" for _ in labels], values=sales, color=labels, color_discrete_sequence=colors)
    st.plotly_chart(fig_treemap, use_container_width=True)

# -----------------------------
# 산점도 대시보드
# -----------------------------
def show_scatter_dashboard():
    sales = [272, 147, 217, 292, 423, 301, 334, 390, 355, 410, 398, 450]
    costs = [149, 227, 293, 335, 197, 280, 300, 310, 250, 270, 260, 290]
    profits = [s - c for s, c in zip(sales, costs)]
    avg_cost = sum(costs) / len(costs)
    avg_sales = sum(sales) / len(sales)

    st.subheader("① 기본 산점도")
    fig_basic = px.scatter(x=costs, y=sales, labels={'x': '비용', 'y': '매출'})
    st.plotly_chart(fig_basic, use_container_width=True)

    st.subheader("② 회귀선 포함 산점도")
    fig_reg = px.scatter(x=costs, y=sales, labels={'x': '비용', 'y': '매출'}, trendline="ols")
    st.plotly_chart(fig_reg, use_container_width=True)

    st.subheader("③ 수익성 버블 차트")
    fig_bubble = px.scatter(x=costs, y=sales, size=[abs(p) for p in profits], color=["수익" if p >= 0 else "손실" for p in profits], labels={'x': '비용', 'y': '매출'})
    st.plotly_chart(fig_bubble, use_container_width=True)

    st.subheader("④ 사분면 분석 차트")
    categories = []
    for s, c in zip(sales, costs):
        if s >= avg_sales and c < avg_cost:
            categories.append("스타 제품")
        elif s >= avg_sales and c >= avg_cost:
            categories.append("프리미엄 전략")
        elif s < avg_sales and c < avg_cost:
            categories.append("니치 시장")
        else:
            categories.append("개선 필요")
    fig_quad = px.scatter(x=costs, y=sales, color=categories, labels={'x': '비용', 'y': '매출'})
    fig_quad.add_shape(type="line", x0=avg_cost, x1=avg_cost, y0=min(sales), y1=max(sales), line=dict(dash="dash"))
    fig_quad.add_shape(type="line", x0=min(costs), x1=max(costs), y0=avg_sales, y1=avg_sales, line=dict(dash="dash"))
    st.plotly_chart(fig_quad, use_container_width=True)

# -----------------------------
# 파레토차트 대시보드
# -----------------------------
def show_pareto_dashboard():
    departments = ['기획부', '마케팅부', '영업부', '인사부', '개발부']
    training_hours = [87, 87, 84, 67, 64]
    sales = [954, 923, 559, 477, 209]

    st.subheader("① 파레토 차트")
    sorted_data = sorted(zip(departments, sales), key=lambda x: x[1], reverse=True)
    sorted_depts = [x[0] for x in sorted_data]
    sorted_sales = [x[1] for x in sorted_data]
    total_sales = sum(sorted_sales)
    cumulative = []
    cum_sum = 0
    for val in sorted_sales:
        cum_sum += val
        cumulative.append(round(cum_sum / total_sales * 100, 1))
    fig_pareto = go.Figure()
    fig_pareto.add_trace(go.Bar(x=sorted_depts, y=sorted_sales, name="매출", yaxis="y"))
    fig_pareto.add_trace(go.Scatter(x=sorted_depts, y=cumulative, name="누적 기여율", mode="lines+markers", yaxis="y2"))
    fig_pareto.update_layout(yaxis=dict(title="매출"), yaxis2=dict(title="누적 기여율(%)", overlaying="y", side="right", range=[0, 100]))
    st.plotly_chart(fig_pareto, use_container_width=True)

    st.subheader("② 교육 훈련 시간 vs 매출")
    fig_scatter = px.scatter(x=training_hours, y=sales, text=departments, labels={'x': '교육 훈련 시간', 'y': '매출'})
    fig_scatter.update_traces(textposition='top center')
    st.plotly_chart(fig_scatter, use_container_width=True)

    st.subheader("③ 단위 훈련 시간당 매출")
    efficiency = [round(s / t, 2) for s, t in zip(sales, training_hours)]
    fig_eff = go.Figure([go.Bar(x=departments, y=efficiency)])
    fig_eff.update_layout(yaxis_title="매출/시간")
    st.plotly_chart(fig_eff, use_container_width=True)

# -----------------------------
# 메인 탭 (정확히 5개, 시트명과 동일)
# -----------------------------
st.title("엑셀 시트별 대시보드")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["바차트_히스토그램", "시계열차트", "파이차트", "산점도", "파레토차트"])

with tab1:
    show_bar_histogram_dashboard()
with tab2:
    show_timeseries_dashboard()
with tab3:
    show_piechart_dashboard()
with tab4:
    show_scatter_dashboard()
with tab5:
    show_pareto_dashboard()
