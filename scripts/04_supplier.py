"""阶段4：供应商履约绩效评分卡 + ABC 分级
严格按 docs/口径文档.md v1.1 §9：
- 门槛：同一供应商交付行数 ≥10 才入评，低频单列观察名单
- 指标：OTD% + 平均延迟(仅迟交样本) + 交付金额 + 频次
- min-max 归一化；权重 OTD 40% / 延迟 30% / 金额 20% / 频次 10%
- ABC 分级按交付金额帕累托：A=累计前70%，B=70-90%，C=90-100%
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_cleaned

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

df = load_cleaned()
df["late_delay"] = df["delay_days"].where(df["delay_days"] > 0)
md = []

# ===================== 1. 指标聚合 =====================
ven = df.groupby("Vendor").agg(
    lines=("ID", "size"),
    asn=("ASN/DN #", "nunique"),
    otd=("ot_bool", lambda s: 100 * s.mean()),
    avg_late=("late_delay", "mean"),
    late_n=("late_delay", "count"),
    value=("line_value", "sum"),
).reset_index()
ven["avg_late"] = ven["avg_late"].fillna(0)

MIN_N = 10
scored = ven[ven["lines"] >= MIN_N].copy()
watch = ven[ven["lines"] < MIN_N].copy()

md.append(f"## 1. 评分门槛与样本\n")
md.append(f"- 供应商总数：{len(ven)}；入评（行数≥{MIN_N}）：**{len(scored)}** 家；观察名单（不评分）：{len(watch)} 家。")
md.append(f"- 频次口径：`lines`=交付订单行数（另附 `asn`=发货单数，供参考）。")
md.append(f"- 注：`SCMS from RDC` 是区域配送中心出货渠道（非制造型供应商），体量与频次极大，评分中按同一口径纳入，结论解读时单独提示。")
md.append("")

# ===================== 2. min-max 归一化 + 权重 =====================
def norm_pos(s):
    r = s.max() - s.min()
    return 100.0 if r <= 0 else (s - s.min()) / r * 100

def norm_neg(s):
    r = s.max() - s.min()
    return 100.0 if r <= 0 else (s.max() - s) / r * 100

scored = scored.copy()
scored["s_otd"] = scored["otd"]
scored["s_delay"] = norm_neg(scored["avg_late"])
scored["s_value"] = norm_pos(scored["value"])
scored["s_freq"] = norm_pos(scored["lines"])

W = {"otd": 0.40, "delay": 0.30, "value": 0.20, "freq": 0.10}
scored["score"] = (W["otd"] * scored["s_otd"] + W["delay"] * scored["s_delay"]
                   + W["value"] * scored["s_value"] + W["freq"] * scored["s_freq"])
scored = scored.sort_values("score", ascending=False).reset_index(drop=True)
scored["rank"] = scored.index + 1

# ===================== 3. ABC 分级（金额帕累托） =====================
ven_abc = ven.sort_values("value", ascending=False).reset_index(drop=True)
ven_abc["cum"] = ven_abc["value"].cumsum() / ven_abc["value"].sum()
ven_abc["ABC"] = np.select(
    [ven_abc["cum"] <= 0.70, ven_abc["cum"] <= 0.90], ["A", "B"], default="C")
abc_map = ven_abc.set_index("Vendor")["ABC"]
scored["ABC"] = scored["Vendor"].map(abc_map)
watch["ABC"] = watch["Vendor"].map(abc_map)

md.append("## 2. 权重设定理由\n")
md.append("| 指标 | 权重 | 理由 |")
md.append("|---|---|---|")
md.append("| OTD% | 40% | 项目核心目标是准时交付，优先级最高 |")
md.append("| 平均延迟(迟交样本) | 30% | 衡量『迟到有多严重』，是准时率的强度补充 |")
md.append("| 交付金额 | 20% | 体量越大、供应越关键，占比次要但不可忽略 |")
md.append("| 频次 | 10% | 交付稳定性参考，弱权重避免规模重复计权 |")
md.append("")
md.append("各指标 min-max 归一化到 0–100（延迟越低分越高），加权得综合分。\n")

# ===================== 4. 评分卡（前 20 + 末 10） =====================
show_cols = ["rank", "Vendor", "ABC", "lines", "asn", "otd", "avg_late", "late_n", "value", "score"]
md.append("## 3. 评分卡（综合分 Top 20）\n")
md.append("| 排名 | 供应商 | ABC | 行数 | 发货单 | OTD% | 平均迟到(天) | 迟到行数 | 金额(USD) | 综合分 |")
md.append("|---|---|---|---|---|---|---|---|---|---|---|")
for _, r in scored.head(20).iterrows():
    md.append(f"| {int(r['rank'])} | {r['Vendor']} | {r['ABC']} | {int(r['lines'])} | {int(r['asn'])} | {r['otd']:.1f} | {r['avg_late']:.1f} | {int(r['late_n'])} | {r['value']:,.0f} | {r['score']:.1f} |")
md.append("")

md.append("## 4. 评分卡（综合分末 10 家，重点改进候选）\n")
md.append("| 排名 | 供应商 | ABC | 行数 | OTD% | 平均迟到(天) | 迟到行数 | 金额(USD) | 综合分 |")
md.append("|---|---|---|---|---|---|---|---|---|---|")
for _, r in scored.tail(10).iterrows():
    md.append(f"| {int(r['rank'])} | {r['Vendor']} | {r['ABC']} | {int(r['lines'])} | {r['otd']:.1f} | {r['avg_late']:.1f} | {int(r['late_n'])} | {r['value']:,.0f} | {r['score']:.1f} |")
md.append("")

# ===================== 5. ABC 汇总 =====================
abc_sum = ven_abc.groupby("ABC").agg(
    vendors=("Vendor", "size"), value=("value", "sum"),
    lines=("lines", "sum")).reset_index()
total_value = ven_abc["value"].sum()
md.append("## 5. ABC 分级汇总（按金额帕累托）\n")
md.append("| 级别 | 供应商数 | 交付行数 | 金额占比 | 金额(USD) |")
md.append("|---|---|---|---|---|")
for _, r in abc_sum.iterrows():
    md.append(f"| {r['ABC']} | {int(r['vendors'])} | {int(r['lines'])} | {r['value']/total_value*100:.1f}% | {r['value']:,.0f} |")
md.append("")

# ===================== 6. 供应商×国家×产品 交叉 =====================
top_v = scored.head(8)["Vendor"].tolist()
cross = df[df["Vendor"].isin(top_v)].pivot_table(
    index="Vendor", columns="Product Group", values="line_value", aggfunc="sum", fill_value=0)
md.append("## 6. Top8 供应商 × 产品组 交叉（金额 USD）\n")
md.append("| 供应商 | " + " | ".join(cross.columns) + " |")
md.append("|---|" + "|".join(["---"] * len(cross.columns)) + "|")
for v, row in cross.iterrows():
    md.append(f"| {v} | " + " | ".join(f"{x:,.0f}" for x in row) + " |")
md.append("")

# 交叉热力图
fig, ax = plt.subplots(figsize=(9, 6))
sns_hm = cross.div(cross.sum(axis=1), axis=0)
import seaborn as sns
sns.heatmap(sns_hm, annot=True, fmt=".0%", cmap="Blues", ax=ax,
            cbar_kws={"label": "share of vendor value"})
ax.set_title("Top8 vendors: product group mix (value share)")
fig.tight_layout()
fig.savefig(OUT / "fig4_04_cross_heatmap.png", dpi=130)
plt.close(fig)

# ===================== 图表 =====================
# fig4_02 排名柱状图
top_plot = scored.head(20).iloc[::-1]
fig, ax = plt.subplots(figsize=(9, 7))
colors = ["#C44E52" if s < 50 else "#4C72B0" for s in top_plot["score"]]
ax.barh(top_plot["Vendor"], top_plot["score"], color=colors)
ax.set_xlabel("Composite score (0-100)")
ax.set_title("Supplier performance score (top 20)")
fig.tight_layout()
fig.savefig(OUT / "fig4_02_ranking.png", dpi=130)
plt.close(fig)

# fig4_03 气泡图：金额 vs OTD，大小=行数
fig, ax = plt.subplots(figsize=(10, 7))
s = scored["lines"].clip(lower=10)
ax.scatter(scored["otd"], scored["value"], s=s * 0.15, alpha=0.6,
           c=scored["score"], cmap="RdYlGn")
for _, r in scored.head(8).iterrows():
    ax.annotate(r["Vendor"], (r["otd"], r["value"]), fontsize=7)
ax.set_xlabel("OTD %")
ax.set_ylabel("Delivery value (USD)")
ax.set_title("Bubble: value vs on-time (size=lines, color=score)")
fig.tight_layout()
fig.savefig(OUT / "fig4_03_bubble.png", dpi=130)
plt.close(fig)

# fig4_01 雷达图（Top6）
from math import pi
labels = ["OTD", "Low delay", "Value", "Frequency"]
top6 = scored.head(6)
N = len(labels)
angles = [n / N * 2 * pi for n in range(N)]
angles += angles[:1]
fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
for _, r in top6.iterrows():
    vals = [r["s_otd"], r["s_delay"], r["s_value"], r["s_freq"]]
    vals += vals[:1]
    ax.plot(angles, vals, linewidth=2, label=r["Vendor"])
    ax.fill(angles, vals, alpha=0.08)
ax.set_xticks(angles[:-1])
ax.set_xticklabels(labels)
ax.set_ylim(0, 100)
ax.set_title("Top6 suppliers radar (normalized 0-100)")
ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "fig4_01_radar.png", dpi=130)
plt.close(fig)

# ===================== 输出 xlsx =====================
score_out = scored[["rank", "Vendor", "ABC", "lines", "asn", "otd", "avg_late",
                    "late_n", "value", "s_otd", "s_delay", "s_value", "s_freq", "score"]]
watch_out = watch[["Vendor", "ABC", "lines", "asn", "otd", "avg_late", "value"]]
with pd.ExcelWriter(OUT / "供应商评分卡.xlsx", engine="openpyxl") as w:
    score_out.to_excel(w, sheet_name="评分卡", index=False)
    watch_out.to_excel(w, sheet_name="观察名单(<10行)", index=False)
    abc_sum.to_excel(w, sheet_name="ABC汇总", index=False)

(OUT / "阶段4_供应商绩效.md").write_text("\n".join(md) + "\n", encoding="utf-8")
print(f"阶段4完成：入评 {len(scored)} 家，观察 {len(watch)} 家")
print(f"评分卡 xlsx 已输出，Top5: ", ", ".join(scored.head(5)['Vendor']))
for f in sorted(OUT.glob("fig4_*.png")):
    print(" 图表", f.name)
