# Power BI 看板接入指南

> 数据源：本机 MySQL（`scms_bi` 只读账号，仅 `ads` / `dim` 可见）；口径见 `measures.md`。

## 0. 前置

1. 安装 Power BI Desktop（`winget install Microsoft.PowerBI`）。
2. 安装 MySQL ODBC 驱动（Power BI 连 MySQL 需 Connector/ODBC）：
   - `winget install Oracle.MySQL`（含 Connector/NET），或下载 MySQL Connector/ODBC。
3. 确认 `config/.env` 中 `scms_bi` 账号可用。

## 1. 连接 MySQL

1. Power BI Desktop → 获取数据 → **MySQL 数据库**。
2. 服务器 `127.0.0.1:3306`，数据库选 `scms_dw` 语义视图，账号 `scms_bi`（只读）。
3. 选择需要的表/视图：
   - `ads.v_supplier_scorecard`、`ads.v_abc_summary`
   - `dws.v_otd_by_mode`、`dws.v_otd_by_country`、`dws.v_cycle_summary`、`dws.v_unit_freight_by_mode`、`dws.v_monthly_summary`

## 2. 建两个页面

- **页1 供应商监控**：评分卡排名柱状图（score）、供应商 OTD vs 金额气泡图、ABC 分级环形图、雷达/矩阵。
- **页2 时效成本**：运输方式/国家 OTD 条形图、周期分段中位、单位运费对比、月度 OTD 趋势折线。

度量全部按 `measures.md` 对照表落地，不另算口径。

## 3. 定时刷新边界（重要）

- Power BI **Desktop 仅支持手动刷新**（主页 → 刷新）。
- 真·定时刷新需 **Power BI Service + 数据网关**（企业方案）；本项目本地演示用手动刷新即可。
- ETL/质检/对账的**定时**已由 `deploy/register_task.ps1`（Windows 任务计划）承担，与 BI 刷新解耦。

## 4. 故障排查

| 现象 | 排查 |
|---|---|
| 连接被拒 | 检查 MySQL 服务 `MySQL80` 是否 Running；`scms_bi` 密码是否与 `config/.env` 一致 |
| 看不到 dws 表 | `scms_bi` 仅授权 `ads`/`dim`，dws 数据请走 `ads.v_*` 视图（已含 dws 结果） |
| 数字对不上 | 先跑 `uv run python dw/analytics/reconcile.py` 看对账报告；BI 侧是否误加了过滤条件 |
