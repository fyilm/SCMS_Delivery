# SCMS Delivery — 交付供应链绩效分析

对 SCMS（Supply Chain Management System，PEPFAR 下）向非洲及受援国配送 HIV 抗病毒药 / 检测试剂的历史交付数据，做从**数据准备 → 时效分析 → 成本分析 → 供应商绩效 → 综合报告**的全链路分析。

## 数据

- 文件：`data/SCMS_Delivery_History_data.csv`
- 规模：10,324 条单品交货记录（2006–2015，43 国，73 供应商）
- 字段：订单/询价编号、国家、配送渠道、贸易条款、运输方式、5 个日期、产品属性、数量/金额/单价、重量、运费、保险费（共 33 列）

## 项目结构

```
SCMS_Delivery/
├── data/                  # 原始数据（只读）
├── docs/
│   ├── 口径文档.md         # 指标口径 v1.1（所有计算的强制规范）
│   └── 清洗决策表.md       # 字段→问题→处理→影响行数
├── scripts/               # 可复现脚本（uv run 执行）
│   ├── common.py          # 清洗后数据集标准加载器
│   ├── 01_prepare.py      # 阶段1：清洗 + 特征工程
│   ├── 02_timeliness.py   # 阶段2：交付时效 + 统计检验
│   ├── 03_cost.py         # 阶段3：成本结构 + 运费回归
│   ├── 04_supplier.py     # 阶段4：供应商评分卡 + ABC 分级
│   └── 05_report.py       # 阶段5：透视表复现核心结论
├── output/                # 清洗数据 + 图表 + 评分卡 + 分阶段结论
├── report/                # 综合报告（本地生成，不入库）
├── pyproject.toml / uv.lock
└── .gitignore
```

## 环境与复现

依赖由 [uv](https://docs.astral.sh/uv/) 管理（锁文件 `uv.lock` 固定版本，Python ≥ 3.12）。

```bash
uv sync                       # 安装依赖
uv run python scripts/01_prepare.py   # 阶段1：清洗 + 决策表 + 数据概况
uv run python scripts/02_timeliness.py
uv run python scripts/03_cost.py
uv run python scripts/04_supplier.py
uv run python scripts/05_report.py    # 生成 report/透视表.xlsx
```

依赖：pandas、matplotlib、seaborn、scipy、statsmodels、scikit-posthocs、openpyxl。

## 方法论要点

- **口径先行**：所有指标先定义后计算（`docs/口径文档.md`），任何口径未覆盖情况先停先问。
- **缺失/特殊值只标记不静默删除**：`N/A`、`Pre-PQ Process`、`N/A - From RDC` 等业务状态保留为独立类别并单独计数。
- **统计规范**：组间比较用 Kruskal-Wallis + Dunn 两两（BH-FDR 校正）；每结论附方法 + 统计量 + p 值 + 样本量；不显著不写「显著」。
- **回归口径**：因变量 `log1p(unit_freight)`，剔除文本标记行，one-hot + 参照组，连续变量 winsorize ±1%；结论只作关联、不作因果。
- **供应商评分**：门槛 ≥10 行；指标 OTD / 平均迟到 / 金额 / 频次 min-max 归一化，权重 40/30/20/10；ABC 分级按金额帕累托。

## 核心结论

- 准时交付率 **OTD 88.51%**，但长尾严重（迟到中位 12 天、p99 164 天）。
- 延迟显著因子：运输方式（Ocean 82.5% vs Air 90.4%）与 RDC 链路（82.8%）；国家差异大（Vietnam 99.1% vs Congo DRC 75.1%）。
- 采购周期瓶颈在「下单→计划」段（中位 92 天，占全程约 60%）。
- 运费回归 R²=0.675：由重量规模效应（log_weight 系数 -0.45）与运输方式主导，Air 单位运费约为 Ocean 的 6 倍。
- 供应商高度集中：`SCMS from RDC` 占交付金额 66.7%；Aurobindo 为「大体量 + 低准时」首要整改对象。

> 更多细节见 `report/`（综合报告 / Top5 Insights / 面试拷问清单），该目录按约定不入库，本地运行阶段 1–5 后生成。

## 说明

本仓库仅用于数据分析练习与学习，结论为基于历史数据的描述性与关联性分析，不构成对 SCMS 或任何组织的业务评价。
