# BI 度量口径对照表（度量 → SQL 视图 → 口径文档）

> 所有 Power BI 度量均指向 MySQL 语义视图（`ads.v_*` / `dws.v_*`），口径与 `docs/口径文档.md` 逐条对齐，禁止在 Power BI 内另算口径。

## 看板一：供应商监控（数据源 `ads.v_supplier_scorecard` / `ads.v_abc_summary`）

| 度量名 | DAX | SQL 来源 | 口径文档条款 |
|---|---|---|---|
| 综合评分 | `MAX(v_supplier_scorecard[score])` | `ads.supplier_scorecard.score` | §1 供应商评分（权重 40/30/20/10，min-max） |
| 准时率 OTD% | `MAX(v_supplier_scorecard[otd])` | `ads.supplier_scorecard.otd` | §1 `ot_bool = delay≤0` 无容忍窗口 |
| 平均迟到(天) | `MAX(v_supplier_scorecard[avg_late])` | `ads.supplier_scorecard.avg_late` | §1 仅迟交样本均值 |
| 交付金额 | `SUM(v_supplier_scorecard[total_value])` | `ads.supplier_scorecard.total_value` | §2 字段 25 Line Item Value |
| ABC 级别 | `MAX(v_supplier_scorecard[abc])` | `ads.supplier_scorecard.abc` | §1 ABC 按金额帕累托 A≤70% B≤90% |
| ABC 供应商数 | `SUM(v_abc_summary[vendor_cnt])` | `ads.abc_summary.vendor_cnt` | §1 |

## 看板二：时效与成本（数据源 `dws.v_otd_by_mode` / `v_otd_by_country` / `v_cycle_summary` / `v_unit_freight_by_mode` / `v_monthly_summary`）

| 度量名 | DAX | SQL 来源 | 口径文档条款 |
|---|---|---|---|
| 运输方式准时率 | `SUM(v_otd_by_mode[otd_pct])`（按 shipment_mode 分组展示） | `dws.otd_by_mode` | §1 准时率 |
| 国家准时率 | `SUM(v_otd_by_country[otd_pct])` | `dws.otd_by_country` | §1 |
| 周期中位天数 | `SUM(v_cycle_summary[median_days])`（按 cycle_seg） | `dws.cycle_summary` | §1 cycle 三段+总周期 |
| 单位运费中位 | `SUM(v_unit_freight_by_mode[median_freight])` | `dws.unit_freight_by_mode` | §1 unit_freight 分母保护 |
| 月度准时率趋势 | `SUM(v_monthly_summary[otd_pct])` | `dws.monthly_summary` | §1 |

> 说明：视图已按口径物化，Power BI 侧仅做「取数 + 展示 + 切片」，不做二次指标计算，保证与对账结论一致（`output/对账报告.md`）。
