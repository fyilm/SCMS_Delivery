"""SCMS 供应商绩效查询前端（Streamlit）。

前置：先启动 FastAPI 服务  `uv run uvicorn api.main:app --port 8000`
运行：`uv run streamlit run api/dashboard.py`
"""
import os

import httpx
import streamlit as st

BASE = os.environ.get("SCMS_API_BASE", "http://127.0.0.1:8000")

st.set_page_config(page_title="SCMS 供应商绩效查询", page_icon="📦", layout="wide")
st.title("SCMS 供应商绩效查询")
st.caption("数据源：MySQL 五层数仓 ADS 应用层 · 接口：FastAPI")

with st.sidebar:
    st.header("查询条件")
    name = st.text_input("供应商名（精确匹配）", placeholder="如 SCMS from RDC")
    do_query = st.button("查询评分卡", type="primary")
    st.divider()
    st.subheader("供应商列表")
    try:
        rows = httpx.get(f"{BASE}/api/v1/suppliers", params={"limit": 100}, timeout=5).json()
        pick = st.selectbox("选择供应商", [""] + [r["vendor"] for r in rows])
        if pick and not name:
            name = pick
    except Exception:
        st.warning("无法连接后端，请先启动 FastAPI 服务")


def show_score(d: dict):
    st.success(f"{d['vendor']}　综合评分 **{d['score']}**（第 {d['score_rank']} 名 / ABC 级 {d['abc']}）")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("准时率 OTD", f"{float(d['otd']):.1f}%")
    c2.metric("平均迟到", f"{float(d['avg_late']):.1f} 天")
    c3.metric("交付行数", f"{d['line_cnt']:,}")
    c4.metric("交付金额", f"${float(d['total_value']):,.0f}")
    st.progress(min(float(d['score']) / 100, 1.0))


if do_query or (name and st.session_state.get("auto", False)):
    if not name:
        st.info("请输入或选择供应商名")
    else:
        try:
            r = httpx.get(f"{BASE}/api/v1/suppliers/{name}/score", timeout=5)
            if r.status_code == 200:
                show_score(r.json())
            elif r.status_code == 404:
                st.warning(r.json().get("detail", "未找到该供应商"))
            else:
                st.error(f"服务返回 {r.status_code}")
        except httpx.ConnectError:
            st.error(f"无法连接后端 {BASE}，请先运行：uv run uvicorn api.main:app --port 8000")

if name and not do_query:
    try:
        r = httpx.get(f"{BASE}/api/v1/suppliers/{name}/score", timeout=5)
        if r.status_code == 200:
            show_score(r.json())
    except Exception:
        pass
