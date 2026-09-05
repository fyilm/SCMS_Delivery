"""阶段3：物流成本结构分析 + 运费驱动因子回归
严格按 docs/口径文档.md v1.1：
- 回归前先输出 unit_freight 分位数表 sanity check（> $10,000/kg 不进模型）
- 剔除 freight_flag≠numeric 与 weight 缺失行；one-hot + 参照组；因变量 log1p；连续自变量 winsorize ±1%
- 表述保守：仅『关联/驱动因素』，不作因果
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from scipy.stats.mstats import winsorize
import statsmodels.formula.api as smf
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_cleaned

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
sns.set_theme(style="whitegrid", context="notebook")

df = load_cleaned()
md = []

# ===================== 1. Freight 总体分布与异常值 =====================
fn = df["freight_numeric"].dropna()
md.append("## 1. Freight Cost 总体分布\n")
md.append(f"- 数值样本：{len(fn)} 行（另有 included 1442 / invoiced 239 / reference 2445 未参与数值统计）")
md.append(f"- Freight 分布：中位数 ${fn.median():,.0f}，均值 ${fn.mean():,.0f}，p95=${fn.quantile(0.95):,.0f}，max=${fn.max():,.0f}")
md.append(f"- IQR 离群标记 flag_freight_numeric_outlier 行数：{int(df['flag_freight_numeric_outlier'].sum())}")
md.append("")

# ===================== 2. unit_freight sanity check =====================
uf = df["unit_freight"].dropna()
md.append("## 2. unit_freight 分位数 sanity check（回归前）\n")
q = uf.quantile([0.5, 0.75, 0.9, 0.95, 0.99, 0.999])
md.append("| 分位 | 50% | 75% | 90% | 95% | 99% | 99.9% |")
md.append("|---|---|---|---|---|---|---|")
md.append("| $/kg | " + " | ".join(f"{q[p]:,.2f}" for p in [0.5, 0.75, 0.9, 0.95, 0.99, 0.999]) + " |")
extreme_n = int(df["flag_unit_freight_extreme"].sum())
md.append(f"- unit_freight > $10,000/kg 的行数：**{extreme_n}**，已标记 flag_unit_freight_extreme，**不进回归**，仅在描述性统计呈现。")
md.append("")

# ===================== 3. unit_freight 按运输方式/INCO =====================
md.append("## 3. unit_freight 按运输方式与贸易条款（描述性）\n")
for col in ["Shipment Mode", "Vendor INCO Term"]:
    g = df.dropna(subset=["unit_freight"]).groupby(col)["unit_freight"].agg(
        n="size", median="median", mean="mean", p90=lambda s: s.quantile(0.9))
    md.append(f"| {col} | n | 中位数 $/kg | 均值 $/kg | p90 $/kg |")
    md.append("|---|---|---|---|---|")
    for k, r in g.sort_values("median").iterrows():
        md.append(f"| {k} | {int(r['n'])} | {r['median']:.2f} | {r['mean']:.2f} | {r['p90']:.2f} |")
    md.append("")

# ===================== 4. 回归模型 =====================
reg = df[(df["freight_flag"] == "numeric") & df["weight_numeric"].notna()].copy()
reg = reg[reg["unit_freight"].notna() & (reg["unit_freight"] <= 10_000)].copy()
reg["log_uf"] = np.log1p(reg["unit_freight"])
reg["log_weight"] = np.log(reg["weight_numeric"].clip(lower=1e-6))
reg["log_value"] = np.log1p(reg["line_value"].clip(lower=0))
# winsorize ±1% 连续自变量
reg["log_weight_w"] = winsorize(reg["log_weight"], limits=[0.01, 0.01])
reg["log_value_w"] = winsorize(reg["log_value"], limits=[0.01, 0.01])
reg["year_c"] = reg["delivery_year"] - 2006

md.append(f"## 4. 运费驱动因子回归（因变量 log1p(unit_freight)）\n")
md.append(f"- 回归样本：freight_flag=numeric 且 weight 有效且 unit_freight≤$10,000/kg → **n={len(reg)}**")
md.append(f"- 参照组：Shipment Mode=Air、INCO=EXW、Product Group=ARV（drop_first）")
md.append(f"- 连续自变量 log_weight、log_value 均 winsorize ±1%；year 已中心化(减2006)。")
md.append("- 说明：此为**关联模型**，系数反映伴随关系，不作因果解读。\n")

model = smf.ols(
    "log_uf ~ log_weight_w + log_value_w + "
    "C(Shipment_Mode, Treatment('Air')) + "
    "C(INCO, Treatment('EXW')) + "
    "C(group, Treatment('ARV')) + year_c",
    data=reg.rename(columns={"Shipment Mode": "Shipment_Mode",
                             "Vendor INCO Term": "INCO",
                             "Product Group": "group"})
).fit()

md.append(f"- R²={model.rsquared:.3f}，adj-R²={model.rsquared_adj:.3f}，n={int(model.nobs)}，F={model.fvalue:.1f}")
md.append("")
md.append("| 变量 | 系数 | 95% CI | exp(系数) | p 值 |")
md.append("|---|---|---|---|---|")
for name, row in model.params.items():
    ci = model.conf_int().loc[name]
    e = np.exp(row)
    pv = model.pvalues[name]
    md.append(f"| {name} | {row:.4f} | [{ci[0]:.4f}, {ci[1]:.4f}] | {e:.3f} | {pv:.3g} |")
md.append("")
md.append("> **保守性提示**：INCO 的 CIF(n=2)/DAP(n=3)/DDU(n=2) 样本极少，其系数置信区间宽、不稳定，仅作参考不作结论；")
md.append("> 主要可读结论集中在样本充足的 Air/Ocean/Truck、EXW/CIP/DDP/FCA 与 ARV/HRDT 组。")

# 系数图
ci = model.conf_int()
coef = model.params
names = coef.index
order = coef.sort_values().index
fig, ax = plt.subplots(figsize=(9, 7))
y = np.arange(len(order))
ax.errorbar(coef[order], y, xerr=[coef[order] - ci.loc[order, 0], ci.loc[order, 1] - coef[order]],
            fmt="o", capsize=3, color="#4C72B0")
ax.axvline(0, color="red", ls="--", lw=1)
ax.set_yticks(y)
ax.set_yticklabels(order, fontsize=8)
ax.set_xlabel("Coefficient (log1p $/kg)")
ax.set_title("Freight unit-cost drivers (OLS, 95% CI)")
fig.tight_layout()
fig.savefig(OUT / "fig3_06_coef_plot.png", dpi=130)
plt.close(fig)

# ===================== 5. 保险 vs 货值 =====================
ins = df.dropna(subset=["insurance", "line_value"]).copy()
ins = ins[ins["line_value"] > 0]
ins["ins_rate"] = ins["insurance"] / ins["line_value"]
r, p = stats.spearmanr(ins["line_value"], ins["insurance"])
md.append("## 5. 保险与货值关系\n")
md.append(f"- 保险非零样本 n={int((ins['insurance'] > 0).sum())}（另 {int((ins['insurance'] == 0).sum())} 行保险=0）")
md.append(f"- Spearman 相关（货值 vs 保险额）：ρ={r:.3f}，p={p:.3g}（对数尺度见图 fig3_05）")
md.append(f"- 保险费率（保险/货值）中位数：{ins['ins_rate'].median()*100:.2f}%")
md.append("")

# ===================== 6. 成本构成（货值+运费+保险） =====================
comp = df[df["freight_flag"] == "numeric"].dropna(subset=["line_value", "insurance", "freight_numeric"]).copy()
comp = comp[comp["line_value"] >= 0]
comp["freight_share"] = comp["freight_numeric"] / (comp["line_value"] + comp["freight_numeric"] + comp["insurance"])
md.append("## 6. 成本构成（运费占货值比重）\n")
med_share = comp["freight_share"].median()
md.append(f"- 运费数值行 n={len(comp)}；运费占货值比：中位数 **{med_share*100:.1f}%**（下按运输方式分组）")
g = comp.groupby("Shipment Mode")["freight_share"].agg(n="size", median="median", mean="mean")
md.append("| 运输方式 | n | 运费占货值中位数 | 均值 |")
md.append("|---|---|---|---|")
for k, r in g.sort_values("median").iterrows():
    md.append(f"| {k} | {int(r['n'])} | {r['median']*100:.1f}% | {r['mean']*100:.1f}% |")
md.append("")

# 年度成本构成堆叠图
yearly = comp.groupby("delivery_year").agg(
    commodity=("line_value", "sum"), freight=("freight_numeric", "sum"), insurance=("insurance", "sum"))
fig, ax = plt.subplots(figsize=(10, 5))
yearly.plot(kind="bar", stacked=True, ax=ax, color=["#4C72B0", "#C44E52", "#55A868"])
ax.set_ylabel("USD (million)")
ax.set_xlabel("Year")
ax.set_title("Total spend composition: commodity vs freight vs insurance")
ax.legend(title="Component")
fig.tight_layout()
fig.savefig(OUT / "fig3_04_cost_composition.png", dpi=130)
plt.close(fig)

# ===================== 图表 =====================
# fig3_01 freight vs weight scatter (log-log, by mode)
sc = df.dropna(subset=["freight_numeric", "weight_numeric"])
sc = sc[(sc["freight_numeric"] > 0) & (sc["weight_numeric"] > 0)]
fig, ax = plt.subplots(figsize=(9, 6))
for mode in sc["Shipment Mode"].unique():
    sub = sc[sc["Shipment Mode"] == mode]
    ax.scatter(sub["weight_numeric"], sub["freight_numeric"], s=6, alpha=0.5, label=f"{mode} (n={len(sub)})")
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("Weight (kg, log)")
ax.set_ylabel("Freight cost (USD, log)")
ax.set_title("Freight vs weight by shipment mode (log-log)")
ax.legend(markerscale=3, fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "fig3_01_freight_weight_scatter.png", dpi=130)
plt.close(fig)

# fig3_02 unit_freight box by mode (log y)
ufd = df.dropna(subset=["unit_freight"]).copy()
fig, ax = plt.subplots(figsize=(9, 5))
sns.boxplot(data=ufd, x="Shipment Mode", y="unit_freight", ax=ax,
            hue="Shipment Mode", legend=False, palette="Set2", fliersize=2)
ax.set_yscale("log")
ax.set_ylabel("unit_freight ($/kg, log)")
ax.set_title("Unit freight by shipment mode")
fig.tight_layout()
fig.savefig(OUT / "fig3_02_unit_freight_box_mode.png", dpi=130)
plt.close(fig)

# fig3_03 unit_freight by INCO
fig, ax = plt.subplots(figsize=(10, 5))
sns.boxplot(data=ufd, x="Vendor INCO Term", y="unit_freight", ax=ax,
            hue="Vendor INCO Term", legend=False, palette="Set2", fliersize=2)
ax.set_yscale("log")
ax.tick_params(axis="x", rotation=45)
ax.set_ylabel("unit_freight ($/kg, log)")
ax.set_title("Unit freight by INCO term")
fig.tight_layout()
fig.savefig(OUT / "fig3_03_unit_freight_incoterm.png", dpi=130)
plt.close(fig)

# fig3_05 insurance vs value
ins2 = ins[ins["insurance"] > 0]
fig, ax = plt.subplots(figsize=(8, 6))
ax.scatter(ins2["line_value"], ins2["insurance"], s=5, alpha=0.4)
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("Line item value (USD, log)")
ax.set_ylabel("Insurance (USD, log)")
ax.set_title("Insurance vs cargo value (log-log, insurance>0)")
fig.tight_layout()
fig.savefig(OUT / "fig3_05_insurance_value.png", dpi=130)
plt.close(fig)

(OUT / "阶段3_成本分析.md").write_text("\n".join(md) + "\n", encoding="utf-8")
print("阶段3完成")
print(f" 回归样本 n={len(reg)}, R2={model.rsquared:.3f}")
print(f" unit_freight 极值(>1万/kg): {extreme_n} 行")
for f in sorted(OUT.glob("fig3_*.png")):
    print(" 图表", f.name)
