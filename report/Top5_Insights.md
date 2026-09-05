# Top 5 Insights（每条标注支撑图表 + 关键数字）

> 验收要求：每条 Insight 标注"支撑图表编号 + 关键数字"，并与正文结论逐条对应。

---

**Insight 1 — 准时率看似健康，实则长尾风险**
整体 OTD **88.51%**，但迟到样本中位数 **12 天**、p99 达 **164 天**：约 1,186 行（11.5%）迟到，少数订单严重延误。
- 支撑：`fig2_01_delay_hist.png`（延迟分布长尾）、`输出: 阶段2_时效分析.md §1`
- 关键数字：OTD 88.51%｜迟到中位 12 天｜p99 164 天

**Insight 2 — 运输方式与贸易条款是延迟的显著因子**
准时率 Air 90.4% > Air Charter 88.5% > Truck 83.9% > Ocean 82.5%；INCO 中 CIP 99.6% vs `N/A - From RDC` 82.8%。Kruskal-Wallis 均极显著（p≈1e-137 / 1e-125），Dunn 两两 BH-FDR 全部显著。
- 支撑：`fig2_02_delay_box_mode.png`、`输出: 阶段2_时效分析.md §2/§6`
- 关键数字：Ocean 82.5% vs Air 90.4%；RDC 82.8%

**Insight 3 — 地理差异：最差国集中在中部非洲**
Vietnam 99.1% 最佳、Congo DRC 75.1% 最差（KW p=6.9e-74）；热力图显示中非/内陆国家低准时。
- 支撑：`fig2_03_delay_box_country.png`、`fig2_04_heatmap_country_mode.png`
- 关键数字：Vietnam 99.1% vs Congo DRC 75.1%

**Insight 4 — 采购周期瓶颈在「下单→计划」段，而非最后一公里**
三段周期：询价→下单中位 24 天、下单→计划中位 **92 天**、计划→实际 0 天；总周期中位 155 天。瓶颈在排产/计划段。
- 支撑：`fig2_06_cycle_segments.png`、`输出: 阶段2_时效分析.md §9`
- 关键数字：c2 中位 92 天（占全程约 60%）

**Insight 5 — 运费由「重量规模效应 + 运输方式」主导**
回归 R²=0.675（n=6,171）：`log_weight` 系数 **-0.45**（每 +1% 重量，单位运费约 -0.45%）；Air 单位运费是 Ocean 的约 6 倍（$10.02 vs $1.68/kg）。
- 支撑：`fig3_06_coef_plot.png`、`fig3_01_freight_weight_scatter.png`
- 关键数字：R²=0.675｜log_weight -0.45｜Air $10.02 vs Ocean $1.68/kg

---

**附：候选 Insight 6 — 渠道集中风险**
`SCMS from RDC` 单一渠道占交付金额 **66.7%**（ABC A 级仅 1 家），供应链依赖度高。
- 支撑：`fig4_03_bubble.png`、`输出: 阶段4_供应商绩效.md §5`
- 关键数字：A 级 1 家 = 66.7% 金额
