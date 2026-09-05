# report/ — 综合报告与交付物

本目录为阶段 5 的最终分析产出（本地生成，`scripts/05_report.py` 负责透视表生成）。

## 内容

| 文件 | 说明 |
|---|---|
| `综合报告.md` | 面向业务汇报的完整分析报告（数据→方法→结论→建议） |
| `Top5_Insights.md` | 提炼出的 Top 5 核心洞察（含图表与关键数字引用） |
| `透视表.xlsx` | 7 个工作表复现核心结论：OTD/延迟/周期/运费/供应商等透视 |

## 复现

```bash
uv sync
uv run python scripts/01_prepare.py   # 清洗 → output/scms_cleaned.csv
uv run python scripts/02_timeliness.py
uv run python scripts/03_cost.py
uv run python scripts/04_supplier.py
uv run python scripts/05_report.py    # 重新生成 透视表.xlsx（报告 Markdown 为人工撰写）
```