"""SCMS 全球交付供应链绩效看板（Plotly Dash）。

前置：先启动 FastAPI 后端
      .venv\\Scripts\\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
运行：.venv\\Scripts\\python.exe api/dashboard_dash.py   （默认 http://127.0.0.1:8050）
"""
import os
from urllib.parse import quote

import httpx
import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html

BASE = os.environ.get("SCMS_API_BASE", "http://127.0.0.1:8000")

BG = "#0b0f17"
CARD = "#151b26"
BORDER = "#232c3d"
TEXT = "#e6ebf2"
MUTED = "#8a94a6"
BLUE = "#4c9be8"
GREEN = "#43c59e"
AMBER = "#f2b134"
RED = "#e8734a"

ABC_COLOR = {"A": GREEN, "B": AMBER, "C": "#5b6b82"}

CARD_STYLE = {
    "backgroundColor": CARD,
    "border": f"1px solid {BORDER}",
    "borderRadius": "12px",
    "padding": "12px 14px",
}


_CLIENT = httpx.Client(trust_env=False, timeout=8)


def api(path):
    return _CLIENT.get(f"{BASE}{path}").json()


def load_data():
    try:
        return {
            "kpi": api("/api/v1/summary/kpi"),
            "abc": api("/api/v1/summary/abc"),
            "suppliers": api("/api/v1/suppliers?limit=100"),
            "mode": api("/api/v1/summary/otd-by-mode"),
            "cycle": api("/api/v1/summary/cycle"),
            "freight": api("/api/v1/summary/freight-by-mode"),
            "monthly": api("/api/v1/summary/monthly"),
        }
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


D = load_data()


def style(fig, title, height=330):
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color=TEXT), x=0.02, y=0.95),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=MUTED, size=11),
        margin=dict(l=70, r=24, t=50, b=44),
        height=height,
        template="plotly_dark",
        showlegend=False,
    )
    fig.update_xaxes(gridcolor=BORDER, zeroline=False)
    fig.update_yaxes(gridcolor=BORDER, zeroline=False)
    return fig


def fig_score():
    rows = sorted(D.get("suppliers", []), key=lambda r: r.get("score") or 0,
                  reverse=True)[:15][::-1]
    names = [(r["vendor"][:26] + "…") if len(r["vendor"]) > 27 else r["vendor"] for r in rows]
    fig = go.Figure(go.Bar(
        x=[float(r["score"]) for r in rows],
        y=names,
        orientation="h",
        marker_color=[ABC_COLOR.get(r.get("abc"), BLUE) for r in rows],
        text=[f'{float(r["score"]):.1f}' for r in rows],
        textposition="outside",
        cliponaxis=False,
    ))
    fig.update_xaxes(range=[0, 100])
    return style(fig, "供应商综合评分 Top15（颜色=ABC 级）")


def fig_abc():
    rows = D.get("abc", [])
    fig = go.Figure(go.Pie(
        labels=[f'{r["abc"]} 级（{r["vendor_cnt"]}家）' for r in rows],
        values=[float(r["value_pct"]) for r in rows],
        hole=0.62,
        marker=dict(colors=[ABC_COLOR.get(r["abc"], BLUE) for r in rows],
                    line=dict(color=BG, width=2)),
        textinfo="label+percent",
        textfont=dict(size=12),
    ))
    return style(fig, "ABC 金额占比（帕累托）")


def fig_mode():
    rows = D.get("mode", [])
    fig = go.Figure(go.Bar(
        x=[r["shipment_mode"] for r in rows],
        y=[float(r["otd_pct"]) for r in rows],
        marker_color=BLUE,
        text=[f'{float(r["otd_pct"]):.1f}%' for r in rows],
        textposition="outside",
        cliponaxis=False,
    ))
    fig.update_yaxes(range=[0, 108])
    return style(fig, "各运输方式准时率 OTD%")


def fig_monthly():
    rows = D.get("monthly", [])
    fig = go.Figure(go.Scatter(
        x=[r["year_month"] for r in rows],
        y=[float(r["otd_pct"]) for r in rows],
        mode="lines+markers",
        line=dict(color=GREEN, width=2),
        marker=dict(size=4),
        fill="tozeroy",
        fillcolor="rgba(67,197,158,0.12)",
    ))
    fig.update_yaxes(range=[0, 105])
    return style(fig, "月度准时率趋势")


def fig_cycle():
    rows = D.get("cycle", [])
    fig = go.Figure(go.Bar(
        x=[r["seg_desc"] for r in rows],
        y=[float(r["median_days"]) for r in rows],
        marker_color=AMBER,
        text=[f'{float(r["median_days"]):.0f}天' for r in rows],
        textposition="outside",
        cliponaxis=False,
    ))
    return style(fig, "采购周期分段中位天数")


def fig_freight():
    rows = D.get("freight", [])
    fig = go.Figure(go.Bar(
        x=[r["shipment_mode"] for r in rows],
        y=[float(r["median_freight"]) for r in rows],
        marker_color=RED,
        text=[f'${float(r["median_freight"]):.2f}' for r in rows],
        textposition="outside",
        cliponaxis=False,
    ))
    return style(fig, "各运输方式单位运费中位（$/kg）")


def kpi_cards():
    k = {r["kpi"]: r["kpi_value"] for r in D.get("kpi", [])}
    abc = {r["abc"]: r["vendor_cnt"] for r in D.get("abc", [])}

    def card(label, value, accent):
        return html.Div([
            html.Div(label, style={"color": MUTED, "fontSize": "12px"}),
            html.Div(value, style={"color": accent, "fontSize": "24px",
                                   "fontWeight": "700", "marginTop": "4px"}),
        ], style={**CARD_STYLE, "flex": "1", "minWidth": "150px"})

    return [
        card("总交付行数", f'{int(float(k.get("total_lines", 0))):,}', BLUE),
        card("准时交付率 OTD", f'{float(k.get("otd_pct", 0)):.2f}%', GREEN),
        card("迟到中位(天)", f'{float(k.get("median_late_days", 0)):.0f}', AMBER),
        card("迟到 P99(天)", f'{float(k.get("p99_late_days", 0)):.0f}', RED),
        card("A 级供应商", f'{int(abc.get("A", 0))}', GREEN),
    ]


suppliers = D.get("suppliers", [])
dd_options = [{"label": r["vendor"], "value": r["vendor"]} for r in suppliers]

app = Dash(__name__, title="SCMS 供应链绩效看板")

app.layout = html.Div(
    style={"backgroundColor": BG, "minHeight": "100vh", "padding": "24px 28px",
           "fontFamily": "Segoe UI, Microsoft YaHei, sans-serif", "color": TEXT},
    children=[
        html.H1("SCMS 全球交付供应链绩效看板",
                style={"margin": "0", "fontSize": "26px", "fontWeight": "700"}),
        html.P("数据源：MySQL 五层数仓（ADS/DWS） · 服务：FastAPI · 前端：Plotly Dash",
               style={"color": MUTED, "marginTop": "6px", "fontSize": "13px"}),
        html.Div(id="err", children=(
            html.Div(f"⚠ 无法连接后端 {BASE}：{D['error']}",
                     style={**CARD_STYLE, "color": RED, "marginTop": "16px"})
            if "error" in D else None)),
        html.Div(kpi_cards(), style={"display": "flex", "gap": "16px",
                                     "flexWrap": "wrap", "margin": "20px 0"}),
        html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1fr",
                        "gap": "16px"}, children=[
            html.Div(dcc.Graph(figure=fig_score(), config={"displayModeBar": False}),
                     style=CARD_STYLE),
            html.Div(dcc.Graph(figure=fig_abc(), config={"displayModeBar": False}),
                     style=CARD_STYLE),
            html.Div(dcc.Graph(figure=fig_mode(), config={"displayModeBar": False}),
                     style=CARD_STYLE),
            html.Div(dcc.Graph(figure=fig_monthly(), config={"displayModeBar": False}),
                     style=CARD_STYLE),
            html.Div(dcc.Graph(figure=fig_cycle(), config={"displayModeBar": False}),
                     style=CARD_STYLE),
            html.Div(dcc.Graph(figure=fig_freight(), config={"displayModeBar": False}),
                     style=CARD_STYLE),
        ]),
        html.H2("供应商评分卡查询", style={"fontSize": "18px", "marginTop": "28px"}),
        dcc.Dropdown(id="supplier-dd", options=dd_options, placeholder="选择供应商…",
                     style={"color": "#111", "maxWidth": "560px", "marginTop": "8px"}),
        html.Div(id="detail", style={"marginTop": "16px"}),
    ],
)


@app.callback(Output("detail", "children"), Input("supplier-dd", "value"))
def show_detail(name):
    if not name:
        return html.Div("从上方下拉框选择一个供应商，查看其评分卡。",
                        style={"color": MUTED, "fontSize": "13px"})
    try:
        d = api(f"/api/v1/suppliers/{quote(name)}/score")
    except Exception as e:  # noqa: BLE001
        return html.Div(f"查询失败：{e}", style={"color": RED})
    if not isinstance(d, dict) or "vendor" not in d:
        return html.Div("未找到该供应商。", style={"color": RED})

    def metric(label, value, accent=BLUE):
        return html.Div([
            html.Div(label, style={"color": MUTED, "fontSize": "12px"}),
            html.Div(value, style={"color": accent, "fontSize": "22px",
                                   "fontWeight": "700", "marginTop": "4px"}),
        ], style={**CARD_STYLE, "flex": "1", "minWidth": "140px"})

    return html.Div([
        html.Div(f'{d["vendor"]}　·　第 {d["score_rank"]} 名　·　ABC {d["abc"]} 级',
                 style={"fontSize": "16px", "fontWeight": "600", "marginBottom": "12px"}),
        html.Div(style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}, children=[
            metric("综合评分", f'{float(d["score"]):.1f}', GREEN),
            metric("准时率 OTD", f'{float(d["otd"]):.1f}%'),
            metric("平均迟到(天)", f'{float(d["avg_late"]):.1f}', AMBER),
            metric("交付行数", f'{int(d["line_cnt"]):,}'),
            metric("交付金额", f'${float(d["total_value"]):,.0f}'),
        ]),
    ])


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8050, debug=False)
