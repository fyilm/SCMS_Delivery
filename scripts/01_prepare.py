"""阶段1：数据准备（清洗 + 特征工程 + 清洗决策表 + 数据概况）
严格按 docs/口径文档.md v1.0 执行。
"""
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "SCMS_Delivery_History_data.csv"
OUT = ROOT / "output"
DOCS = ROOT / "docs"
OUT.mkdir(exist_ok=True)

RAW_COLS = [
    "ID", "Project Code", "PQ #", "PO / SO #", "ASN/DN #", "Country",
    "Managed By", "Fulfill Via", "Vendor INCO Term", "Shipment Mode",
    "PQ First Sent to Client Date", "PO Sent to Vendor Date",
    "Scheduled Delivery Date", "Delivered to Client Date",
    "Delivery Recorded Date", "Product Group", "Sub Classification",
    "Vendor", "Item Description", "Molecule/Test Type", "Brand", "Dosage",
    "Dosage Form", "Unit of Measure (Per Pack)", "Line Item Quantity",
    "Line Item Value", "Pack Price", "Unit Price", "Manufacturing Site",
    "First Line Designation", "Weight (Kilograms)", "Freight Cost (USD)",
    "Line Item Insurance (USD)",
]

df = pd.read_csv(RAW, encoding="utf-8-sig", dtype=str)
n_raw = len(df)

# 决策表条目收集器
decisions = []


def record(field, issue, treatment, n):
    decisions.append({"field": field, "issue": issue, "treatment": treatment, "n": n})


# ---- 1. 去重 ----
dup_id = int(df["ID"].duplicated().sum())
record("ID", "主键重复", "保留首条、计数上报", dup_id)
dup_full = int(df.duplicated().sum())
record("全行", "完全重复行", "保留首条、计数上报", dup_full)
key = ["PO / SO #", "Item Description"]
dup_key = int(df.duplicated(subset=key).sum())
record("(PO/SO #, Item Description)", "业务键重复（非完全重复）", "仅计数，不删除", dup_key)
df = df.drop_duplicates().reset_index(drop=True)
n_after_dedup = len(df)

# ---- 2. 日期解析（两套格式 + 业务状态类别，见口径文档 v1.1） ----
pq_raw = df["PQ First Sent to Client Date"].fillna("")
po_raw = df["PO Sent to Vendor Date"].fillna("")

pq_flag = pd.Series("date", index=df.index)
pq_flag[pq_raw == "Pre-PQ Process"] = "pre_pq"
pq_flag[pq_raw == "Date Not Captured"] = "not_captured"
df["pq_flag"] = pq_flag
record("PQ First Sent to Client Date", "Pre-PQ Process（尚未进入询价）", "pq_flag=pre_pq，日期置 NaN", int((pq_flag == "pre_pq").sum()))
record("PQ First Sent to Client Date", "Date Not Captured", "pq_flag=not_captured，日期置 NaN", int((pq_flag == "not_captured").sum()))

po_flag = pd.Series("date", index=df.index)
po_flag[po_raw == "N/A - From RDC"] = "from_rdc"
po_flag[po_raw == "Date Not Captured"] = "not_captured"
df["po_flag"] = po_flag
record("PO Sent to Vendor Date", "N/A - From RDC（区域配送中心出货，无供应商 PO）", "po_flag=from_rdc，日期置 NaN", int((po_flag == "from_rdc").sum()))
record("PO Sent to Vendor Date", "Date Not Captured", "po_flag=not_captured，日期置 NaN", int((po_flag == "not_captured").sum()))

def parse_dates(series, fmt):
    parsed = pd.to_datetime(series, format=fmt, errors="coerce")
    return parsed


pq = parse_dates(pq_raw.where(pq_flag == "date"), "%m/%d/%y")
po = parse_dates(po_raw.where(po_flag == "date"), "%m/%d/%y")
sch, bad_sch = parse_dates(df["Scheduled Delivery Date"], "%d-%b-%y"), 0
delv, bad_delv = parse_dates(df["Delivered to Client Date"], "%d-%b-%y"), 0
rec, bad_rec = parse_dates(df["Delivery Recorded Date"], "%d-%b-%y"), 0

# 实际解析失败（仅在 pq_flag/po_flag == date 的前提下仍未解析成功）
bad_pq = int(((pq_flag == "date") & pq.isna()).sum())
bad_po = int(((po_flag == "date") & po.isna()).sum())
record("PQ First Sent to Client Date", "格式解析失败", "flag_bad_date，日期置 NaN", bad_pq)
record("PO Sent to Vendor Date", "格式解析失败", "flag_bad_date，日期置 NaN", bad_po)

# 世纪推断 sanity check：年份应在 2000-2025 之间
for name, s in [("PQ", pq), ("PO", po), ("Scheduled", sch), ("Delivered", delv), ("Recorded", rec)]:
    bad_year = int(((s.dt.year < 2000) | (s.dt.year > 2025)).sum())
    if bad_year:
        record(f"{name} Date", "年份超出 2000-2025（世纪推断异常）", "flag_bad_date，保留 NaN", bad_year)

record("Scheduled Delivery Date", "解析失败", "→ NaN，计数", bad_sch)
record("Delivered to Client Date", "解析失败", "→ NaN，计数", bad_delv)
record("Delivery Recorded Date", "解析失败", "→ NaN，计数", bad_rec)

df["pq_date"] = pq
df["po_date"] = po
df["scheduled_date"] = sch
df["delivered_date"] = delv
df["recorded_date"] = rec

# ---- 3. Freight 文本标记 ----
freight_raw = df["Freight Cost (USD)"].fillna("")
freight_flag = pd.Series("numeric", index=df.index)
freight_flag[freight_raw == "Freight Included in Commodity Cost"] = "included"
freight_flag[freight_raw == "Invoiced Separately"] = "invoiced"
freight_flag[freight_raw.str.startswith("See ", na=False)] = "reference"
df["freight_flag"] = freight_flag
df["freight_numeric"] = pd.to_numeric(freight_raw.where(freight_flag == "numeric"), errors="coerce")
for f in ["included", "invoiced", "reference"]:
    record("Freight Cost (USD)", f"文本标记 {f}", "映射 freight_flag，数值列置 NaN", int((freight_flag == f).sum()))

# ---- 4. Weight 文本引用 ----
weight_raw = df["Weight (Kilograms)"].fillna("")
weight_text = weight_raw.str.startswith("See ", na=False) & weight_raw.ne("")
df["weight_numeric"] = pd.to_numeric(weight_raw, errors="coerce")
df["flag_weight_reference"] = weight_text
record("Weight (Kilograms)", "文本引用 See DN/ASN (#)", "→ NaN + flag_weight_reference", int(weight_text.sum()))
df.loc[df["weight_numeric"] <= 0, "weight_numeric"] = np.nan
record("Weight (Kilograms)", "数值 ≤ 0", "→ NaN（分母保护）", int((pd.to_numeric(weight_raw, errors="coerce") <= 0).fillna(False).sum()))

# ---- 5. 数值列转换 + 0 值标记 ----
df["qty"] = pd.to_numeric(df["Line Item Quantity"], errors="coerce")
df["line_value"] = pd.to_numeric(df["Line Item Value"], errors="coerce")
df["pack_price"] = pd.to_numeric(df["Pack Price"], errors="coerce")
df["unit_price"] = pd.to_numeric(df["Unit Price"], errors="coerce")
df["insurance"] = pd.to_numeric(df["Line Item Insurance (USD)"], errors="coerce")
df["uom"] = pd.to_numeric(df["Unit of Measure (Per Pack)"], errors="coerce")
df["flag_zero_value"] = df["line_value"] == 0
record("Line Item Value", "数值为 0", "保留 + flag_zero_value", int(df["flag_zero_value"].sum()))

# ---- 6. 异常值标记（IQR×1.5，只标记不删） ----
outlier_cols = {
    "qty": "qty", "line_value": "line_value", "pack_price": "pack_price",
    "unit_price": "unit_price", "weight_numeric": "weight_numeric",
    "freight_numeric": "freight_numeric", "insurance": "insurance",
}
for col in outlier_cols:
    s = df[col]
    lo, hi = s.quantile(0.25), s.quantile(0.75)
    iqr = hi - lo
    mask = (s < lo - 1.5 * iqr) | (s > hi + 1.5 * iqr)
    df[f"flag_{col}_outlier"] = mask
    record(col, "IQR×1.5 离群", f"flag_{col}_outlier，只标记不删", int(mask.sum()))

# ---- 7. 特征工程（按口径） ----
df["delay_days"] = (df["delivered_date"] - df["scheduled_date"]).dt.days
df["ot_bool"] = df["delay_days"] <= 0
df["early_bool"] = df["delay_days"] < 0

df["c1_pq2po"] = (df["po_date"] - df["pq_date"]).dt.days
df["c2_po2sched"] = (df["scheduled_date"] - df["po_date"]).dt.days
df["c3_sched2deliv"] = (df["delivered_date"] - df["scheduled_date"]).dt.days
df["c_total"] = (df["delivered_date"] - df["pq_date"]).dt.days
neg_cycle = (df["c1_pq2po"] < 0) | (df["c2_po2sched"] < 0) | (df["c_total"] < 0)
df["flag_negative_cycle"] = neg_cycle
record("cycle 各段", "负 cycle（PO 早于 PQ 等）", "flag_negative_cycle，均值时排除该段", int(neg_cycle.sum()))

df["unit_freight"] = df["freight_numeric"] / df["weight_numeric"]
df["flag_unit_freight_extreme"] = df["unit_freight"] > 10_000
record("unit_freight", "> $10,000/kg", "flag_unit_freight_extreme，不进回归", int(df["flag_unit_freight_extreme"].sum()))
df["delivery_year"] = df["delivered_date"].dt.year
df["delivery_month"] = df["delivered_date"].dt.to_period("M").astype(str)

# ---- 8. 输出 ----
keep = RAW_COLS + [
    "pq_date", "po_date", "scheduled_date", "delivered_date", "recorded_date",
    "pq_flag", "po_flag",
    "freight_flag", "freight_numeric", "weight_numeric", "flag_weight_reference",
    "qty", "line_value", "pack_price", "unit_price", "insurance", "uom",
    "flag_zero_value", "flag_qty_outlier", "flag_line_value_outlier",
    "flag_pack_price_outlier", "flag_unit_price_outlier", "flag_weight_numeric_outlier",
    "flag_freight_numeric_outlier", "flag_insurance_outlier",
    "delay_days", "ot_bool", "early_bool", "c1_pq2po", "c2_po2sched",
    "c3_sched2deliv", "c_total", "flag_negative_cycle", "unit_freight",
    "flag_unit_freight_extreme", "delivery_year", "delivery_month",
]
df[keep].to_csv(OUT / "scms_cleaned.csv", index=False, encoding="utf-8-sig")

# ---- 9. 清洗决策表（Markdown） ----
rows = "\n".join(
    f"| {d['field']} | {d['issue']} | {d['treatment']} | {d['n']} |"
    for d in decisions
)
md = f"""# 清洗决策表（阶段1）

- 输入行数：{n_raw}；去重后：{n_after_dedup}；输出行数：{n_after_dedup}
- 数据源：`data/SCMS_Delivery_History_data.csv`
- 口径依据：`docs/口径文档.md` v1.1

| 字段 | 问题 | 处理方式 | 影响行数 |
|---|---|---|---|
{rows}
"""
(DOCS / "清洗决策表.md").write_text(md, encoding="utf-8")

# ---- 10. 数据概况报告 ----
overview = f"""# 数据概况报告（阶段1）

- 原始行数：{n_raw}；去重后：{n_after_dedup}
- 原始字段数：{len(RAW_COLS)}；增强后字段数：{len(keep)}
- 国家数：{df['Country'].nunique()}；供应商数：{df['Vendor'].nunique()}
- 产品组分布：{dict(df['Product Group'].value_counts())}
- 子分类分布：{dict(df['Sub Classification'].value_counts())}
- 年份分布（Delivered）：{dict(df['delivery_year'].dropna().astype(int).value_counts().sort_index())}
- delay_days 有效样本：{int(df['delay_days'].notna().sum())}，均值={df['delay_days'].mean():.2f}，中位数={df['delay_days'].median():.2f}
- unit_freight 有效样本：{int(df['unit_freight'].notna().sum())}
- freight_flag 分布：{dict(df['freight_flag'].value_counts())}
"""
(OUT / "数据概况报告.md").write_text(overview, encoding="utf-8")

print(f"原始 {n_raw} 行 -> 去重后 {n_after_dedup} 行")
print(f"输出: {OUT / 'scms_cleaned.csv'} ({len(keep)} 字段)")
print(f"决策表: {DOCS / '清洗决策表.md'} ({len(decisions)} 条规则)")
print("--- delay_days 分位数 ---")
print(df["delay_days"].quantile([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]).round(2))
print("--- unit_freight 分位数 (sanity check) ---")
print(df["unit_freight"].quantile([0.5, 0.9, 0.95, 0.99, 0.999]).round(2))
