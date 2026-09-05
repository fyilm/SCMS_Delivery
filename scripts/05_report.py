"""阶段5：生成透视表 Excel，用于复现报告核心结论（验收：透视表复现）。
输出到 report/（不入 git）。
"""
import numpy as np
import pandas as pd
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_cleaned

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "report"
REPORT.mkdir(exist_ok=True)

df = load_cleaned()
df["late_delay"] = df["delay_days"].where(df["delay_days"] > 0)

sheets = {}

# 1. OTD by shipment mode
g = df.groupby("Shipment Mode").agg(
    n=("ID", "size"),
    OTD_pct=("ot_bool", lambda s: round(100 * s.mean(), 2)),
    median_delay=("delay_days", "median"),
    mean_delay=("delay_days", lambda s: round(s.mean(), 2)),
).reset_index()
sheets["1_OTD_by_mode"] = g

# 2. OTD by product group
g = df.groupby("Product Group").agg(
    n=("ID", "size"),
    OTD_pct=("ot_bool", lambda s: round(100 * s.mean(), 2)),
    median_delay=("delay_days", "median"),
).reset_index()
sheets["2_OTD_by_group"] = g

# 3. OTD by country (n>=100)
cnt = df["Country"].value_counts()
top = cnt[cnt >= 100].index
g = df[df["Country"].isin(top)].groupby("Country").agg(
    n=("ID", "size"),
    OTD_pct=("ot_bool", lambda s: round(100 * s.mean(), 2)),
    median_delay=("delay_days", "median"),
).reset_index().sort_values("OTD_pct", ascending=False)
sheets["3_OTD_by_country"] = g

# 4. unit_freight by mode
uf = df.dropna(subset=["unit_freight"])
g = uf.groupby("Shipment Mode").agg(
    n=("ID", "size"),
    median_usd_kg=("unit_freight", lambda s: round(s.median(), 2)),
    p90_usd_kg=("unit_freight", lambda s: round(s.quantile(0.9), 2)),
).reset_index()
sheets["4_unit_freight_by_mode"] = g

# 5. cycle segments
segs = {
    "c1 询价→下单": "c1_pq2po", "c2 下单→计划": "c2_po2sched",
    "c3 计划→实际": "c3_sched2deliv", "总周期": "c_total",
}
rows = []
for label, col in segs.items():
    s = df[col].dropna()
    s = s[(s >= 0) & (s < 2000)]
    rows.append({"环节": label, "n": len(s), "median": s.median(), "mean": round(s.mean(), 1)})
sheets["5_cycle_segments"] = pd.DataFrame(rows)

# 6. supplier summary (>=10 lines)
ven = df.groupby("Vendor").agg(
    lines=("ID", "size"),
    OTD_pct=("ot_bool", lambda s: round(100 * s.mean(), 2)),
    avg_late_days=("late_delay", "mean"),
    value=("line_value", "sum"),
).reset_index()
ven = ven[ven["lines"] >= 10].sort_values("value", ascending=False)
sheets["6_supplier_summary"] = ven

# 7. freight share by mode
comp = df[(df["freight_flag"] == "numeric")].dropna(subset=["line_value", "freight_numeric"]).copy()
comp = comp[comp["line_value"] >= 0]
comp["freight_share"] = comp["freight_numeric"] / (comp["line_value"] + comp["freight_numeric"])
g = comp.groupby("Shipment Mode")["freight_share"].agg(
    n="size", median_pct=lambda s: round(100 * s.median(), 2)).reset_index()
sheets["7_freight_share_by_mode"] = g

with pd.ExcelWriter(REPORT / "透视表.xlsx", engine="openpyxl") as w:
    for name, s in sheets.items():
        s.to_excel(w, sheet_name=name[:31], index=False)

print("透视表.xlsx 已生成，sheets:", list(sheets.keys()))
