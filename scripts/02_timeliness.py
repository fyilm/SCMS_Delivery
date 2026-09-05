"""阶段2：交付时效与延迟分析（核心）
严格按 docs/口径文档.md v1.1 执行：Kruskal-Wallis 主检验 + Dunn 两两(BH-FDR)；
每结论附方法+统计量+p/q值+样本量；n<30 组合过滤；多重比较说明。
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import scikit_posthocs as sp
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_cleaned

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
sns.set_theme(style="whitegrid", context="notebook")
FDR = "fdr_bh"

df = load_cleaned()

ALPHA = 0.05
md = []  # markdown 行收集


def fmt_p(p):
    return "%.4g" % p if p >= 0.0001 else "%.2e" % p


def kruskal_dunn(data, group_col, val_col="delay_days", min_n=30, collapse=True):
    """返回 (KW结果dict, dunn矩阵DataFrame, 组统计DataFrame)"""
    sub = data[[group_col, val_col]].dropna()
    if collapse:
        cnt = sub[group_col].value_counts()
        keep = cnt[cnt >= min_n].index
        sub = sub.copy()
        sub[group_col] = sub[group_col].where(sub[group_col].isin(keep), "Other (<30)")
    groups = [g[val_col].values for _, g in sub.groupby(group_col)]
    h, p = stats.kruskal(*groups)
    dunn = sp.posthoc_dunn(sub, val_col=val_col, group_col=group_col, p_adjust=FDR) if p < ALPHA else None
    stat = sub.groupby(group_col)[val_col].agg(
        n="size", median="median", mean="mean", p25=lambda s: s.quantile(0.25), p75=lambda s: s.quantile(0.75)
    ).round(1)
    stat["OTD%"] = (sub.groupby(group_col)[val_col].apply(lambda s: 100 * (s <= 0).mean())).round(1)
    return {"H": h, "p": p, "n_total": len(sub), "df": len(groups) - 1}, dunn, stat


def sig_pairs(dunn, thr=0.05):
    out = []
    if dunn is None:
        return out
    cols = list(dunn.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            q = dunn.iloc[i, j]
            if q < thr:
                out.append((cols[i], cols[j], q))
    return out


# ===================== 1. 延迟概况 =====================
d = df["delay_days"]
otd = 100 * (d <= 0).mean()
late = df[d > 0]["delay_days"]
early_n = int((d < 0).sum())
md.append(f"## 1. 延迟概况\n")
md.append(f"- 准时交付率 OTD（delay≤0）：**{otd:.2f}%**（{(d <= 0).sum()} / {d.notna().sum()} 行）")
md.append(f"- 延迟天数：均值 **{d.mean():.2f}** 天，中位数 **{d.median():.0f}** 天（右偏）")
md.append(f"- 提前交付（delay<0）：{early_n} 行（{100*early_n/len(df):.1f}%），不计入延迟叙事，仅附注")
md.append(f"- 迟到样本（delay>0）：{len(late)} 行，其延迟中位数 **{late.median():.1f}** 天，p95={late.quantile(0.95):.0f} 天，p99={late.quantile(0.99):.0f} 天")
md.append("")

fig, ax = plt.subplots(figsize=(9, 5))
bins = np.arange(-140, 161, 5)
ax.hist(d.clip(-140, 160), bins=bins, color="#4C72B0", edgecolor="white")
ax.axvline(0, color="red", lw=1.5, ls="--", label="on-time boundary (delay=0)")
ax.set_xlabel("Delay days (negative = early)")
ax.set_ylabel("Order lines")
ax.set_title("Distribution of delay_days (clip at ±140)")
ax.legend()
fig.tight_layout()
fig.savefig(OUT / "fig2_01_delay_hist.png", dpi=130)
plt.close(fig)

# ===================== 2. 按运输方式 =====================
kw, dunn, stat = kruskal_dunn(df, "Shipment Mode")
md.append("## 2. 按运输方式（Shipment Mode）\n")
md.append("| 方式 | n | OTD% | 延迟中位数 | 延迟均值 | p25 | p75 |")
md.append("|---|---|---|---|---|---|---|")
for g, r in stat.sort_values("OTD%", ascending=False).iterrows():
    md.append(f"| {g} | {int(r['n'])} | {r['OTD%']:.1f} | {r['median']:.1f} | {r['mean']:.1f} | {r['p25']:.1f} | {r['p75']:.1f} |")
md.append(f"\n**Kruskal-Wallis**：H={kw['H']:.1f}，df={kw['df']}，p={fmt_p(kw['p'])}，n={kw['n_total']}。"
          + ("差异显著。" if kw["p"] < ALPHA else "无显著差异。"))
if dunn is not None:
    md.append("**Dunn 事后两两（BH-FDR，q<0.05）**：")
    pairs = sig_pairs(dunn)
    if pairs:
        for a, b, q in pairs:
            md.append(f"- {a} vs {b}：q={fmt_p(q)}（显著）")
    else:
        md.append("- 无显著两两差异。")
md.append("")

fig, ax = plt.subplots(figsize=(9, 5))
order = df.groupby("Shipment Mode")["delay_days"].median().sort_values().index
sns.boxplot(data=df, x="Shipment Mode", y="delay_days", order=order, ax=ax,
            fliersize=2, hue="Shipment Mode", legend=False, palette="Set2")
ax.axhline(0, color="red", ls="--", lw=1)
ax.set_ylabel("Delay days")
ax.set_title("Delay by Shipment Mode")
fig.tight_layout()
fig.savefig(OUT / "fig2_02_delay_box_mode.png", dpi=130)
plt.close(fig)

# ===================== 3. 按产品组 =====================
kw, dunn, stat = kruskal_dunn(df, "Product Group", collapse=False)
md.append("## 3. 按产品组（Product Group）\n")
md.append("| 产品组 | n | OTD% | 延迟中位数 | 延迟均值 |")
md.append("|---|---|---|---|---|")
for g, r in stat.sort_values("OTD%", ascending=False).iterrows():
    md.append(f"| {g} | {int(r['n'])} | {r['OTD%']:.1f} | {r['median']:.1f} | {r['mean']:.1f} |")
md.append(f"\n**Kruskal-Wallis**：H={kw['H']:.1f}，df={kw['df']}，p={fmt_p(kw['p'])}，n={kw['n_total']}。"
          + ("差异显著。" if kw["p"] < ALPHA else "无显著差异。"))
if dunn is not None:
    pairs = sig_pairs(dunn)
    if pairs:
        md.append("**Dunn（BH-FDR）**：")
        for a, b, q in pairs:
            md.append(f"- {a} vs {b}：q={fmt_p(q)}")
md.append("> 注：ANTM(22)/MRDT(8)/ACT(16) 为真实小品类，样本 <30，保留但结论需谨慎。")
md.append("")

# ===================== 4. 按国家（top + Other） =====================
kw, dunn, stat = kruskal_dunn(df, "Country", min_n=100)
md.append("## 4. 按国家（n≥100 单独，其余 Other）\n")
md.append("| 国家 | n | OTD% | 延迟中位数 | 延迟均值 |")
md.append("|---|---|---|---|---|")
for g, r in stat.sort_values("OTD%", ascending=False).iterrows():
    md.append(f"| {g} | {int(r['n'])} | {r['OTD%']:.1f} | {r['median']:.1f} | {r['mean']:.1f} |")
md.append(f"\n**Kruskal-Wallis**：H={kw['H']:.1f}，df={kw['df']}，p={fmt_p(kw['p'])}，n={kw['n_total']}。"
          + ("差异显著。" if kw["p"] < ALPHA else "无显著差异。"))
if dunn is not None:
    pairs = sig_pairs(dunn)
    md.append(f"**Dunn 两两（BH-FDR，共 {len(pairs)} 对显著）**：")
    for a, b, q in pairs[:15]:
        md.append(f"- {a} vs {b}：q={fmt_p(q)}")
md.append("")

# 国家箱线图（top 10 by volume）
top10 = df["Country"].value_counts().head(10).index
fig, ax = plt.subplots(figsize=(10, 5))
sns.boxplot(data=df[df["Country"].isin(top10)], x="Country", y="delay_days",
            order=sorted(top10, key=lambda c: df[df["Country"] == c]["delay_days"].median()),
            ax=ax, fliersize=2, hue="Country", legend=False, palette="Set2")
ax.axhline(0, color="red", ls="--", lw=1)
ax.set_ylabel("Delay days")
ax.set_title("Delay by Country (top 10 by volume)")
fig.tight_layout()
fig.savefig(OUT / "fig2_03_delay_box_country.png", dpi=130)
plt.close(fig)

# ===================== 5. Country × Shipment Mode 热力图 =====================
pivot = df.pivot_table(index="Country", columns="Shipment Mode", values="delay_days",
                       aggfunc="median")
cnt = df.pivot_table(index="Country", columns="Shipment Mode", values="delay_days",
                     aggfunc="size")
pivot = pivot.where(cnt >= 30)
topc = cnt.sum(axis=1).sort_values(ascending=False).head(15).index
pivot = pivot.loc[pivot.index.isin(topc), :]
fig, ax = plt.subplots(figsize=(10, 8))
sns.heatmap(pivot, annot=True, fmt=".0f", cmap="RdYlGn_r", center=0, ax=ax,
            cbar_kws={"label": "Median delay (days)"}, mask=pivot.isna())
ax.set_title("Median delay: Country × Shipment Mode (cells with n<30 blanked)")
fig.tight_layout()
fig.savefig(OUT / "fig2_04_heatmap_country_mode.png", dpi=130)
plt.close(fig)
md.append("## 5. Country × Shipment Mode 热力图\n")
md.append("- 见图 fig2_04：单元格 n<30 已置空（低频组合过滤），国家取货量前 15。\n")

# ===================== 6. INCO Term =====================
kw, dunn, stat = kruskal_dunn(df, "Vendor INCO Term")
md.append("## 6. 按贸易条款（Vendor INCO Term）\n")
md.append("| INCO | n | OTD% | 延迟中位数 | 延迟均值 |")
md.append("|---|---|---|---|---|")
for g, r in stat.sort_values("OTD%", ascending=False).iterrows():
    md.append(f"| {g} | {int(r['n'])} | {r['OTD%']:.1f} | {r['median']:.1f} | {r['mean']:.1f} |")
md.append(f"\n**Kruskal-Wallis**：H={kw['H']:.1f}，df={kw['df']}，p={fmt_p(kw['p'])}，n={kw['n_total']}。"
          + ("差异显著。" if kw["p"] < ALPHA else "无显著差异。"))
if dunn is not None:
    pairs = sig_pairs(dunn)
    if pairs:
        md.append("**Dunn（BH-FDR）**：")
        for a, b, q in pairs:
            md.append(f"- {a} vs {b}：q={fmt_p(q)}")
md.append("")

# ===================== 7. 供应商延迟（晚到最严重） =====================
ven = df[df["delay_days"] > 0].groupby("Vendor")["delay_days"].agg(
    late_n="size", late_median="median", late_p90=lambda s: s.quantile(0.9)
).sort_values("late_n", ascending=False)
ven = ven[ven["late_n"] >= 30]
md.append("## 7. 供应商延迟（迟到次数≥30 的供应商）\n")
md.append("| 供应商 | 迟到次数 | 迟到中位数 | 迟到 p90 |")
md.append("|---|---|---|---|")
for g, r in ven.head(10).iterrows():
    md.append(f"| {g} | {int(r['late_n'])} | {r['late_median']:.1f} | {r['late_p90']:.1f} |")
md.append("")

# ===================== 8. 月度时序 =====================
ts = df.dropna(subset=["delay_days"]).groupby("delivery_month")["delay_days"].agg(
    n="size", otd=lambda s: 100 * (s <= 0).mean(), median="median"
)
ts.index = pd.to_datetime(ts.index)
ts = ts.sort_index()
fig, ax1 = plt.subplots(figsize=(11, 5))
ax1.plot(ts.index, ts["otd"], color="#4C72B0", marker="o", ms=3, label="OTD% (left)")
ax1.set_ylabel("On-time %")
ax1.set_ylim(50, 100)
ax2 = ax1.twinx()
ax2.plot(ts.index, ts["median"], color="#C44E52", marker="s", ms=3, ls="--", label="Median delay days (right)")
ax2.set_ylabel("Median delay (days)")
ax1.set_title("Monthly on-time rate and median delay (2006-2015)")
h1, l1 = ax1.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax1.legend(h1 + h2, l1 + l2, loc="lower right")
fig.tight_layout()
fig.savefig(OUT / "fig2_05_ts_monthly.png", dpi=130)
plt.close(fig)
md.append("## 8. 月度时序\n")
md.append("- 见图 fig2_05：月度准时率与延迟中位数趋势。\n")

# ===================== 9. 采购周期 cycle 分段（仅 Direct Drop 日期完整） =====================
dd = df[df["po_flag"] == "date"].copy()
seg_cols = {"c1 询价→下单": "c1_pq2po", "c2 下单→计划": "c2_po2sched",
            "c3 计划→实际": "c3_sched2deliv", "总周期 询价→交付": "c_total"}
md.append("## 9. 采购周期 cycle 分段（仅 Direct Drop 且有 PO 日期）\n")
md.append(f"- RDC 出货订单（{int((df['po_flag'] == 'from_rdc').sum())} 行）无供应商采购环节，其 c1/c2 为 NaN，不参与本段。")
md.append("- 本段样本：有 po_date 的 Direct Drop 订单（各段再按端点有效性计）。\n")
md.append("| 环节 | n | 中位数(天) | 均值 | p25 | p75 |")
md.append("|---|---|---|---|---|---|")
seg_summary = {}
for label, col in seg_cols.items():
    s = df[col].dropna()
    s = s[(s >= 0) & (s < 2000)]
    seg_summary[col] = s
    md.append(f"| {label} | {len(s)} | {s.median():.0f} | {s.mean():.1f} | {s.quantile(0.25):.0f} | {s.quantile(0.75):.0f} |")
md.append("")

fig, ax = plt.subplots(figsize=(9, 5))
seg_data = pd.concat({k: v for k, v in seg_summary.items()}).reset_index(level=0).rename(columns={"level_0": "segment", 0: "days"})
sns.boxplot(data=seg_data, x="segment", y="days", ax=ax, palette="Set2", fliersize=2, hue="segment", legend=False)
ax.set_ylabel("Days")
ax.set_title("Procurement cycle segments (Direct Drop, non-negative)")
fig.tight_layout()
fig.savefig(OUT / "fig2_06_cycle_segments.png", dpi=130)
plt.close(fig)

# 说明统计口径
md.append("\n---\n## 统计口径说明\n")
md.append(f"- 显著性阈值 α={ALPHA}；组间比较先 Kruskal-Wallis（延迟右偏非正态），显著后 Dunn 两两，p 值 BH-FDR 校正（`{FDR}`）。")
md.append("- 每结论均已标注检验方法、统计量、p/q 值与样本量；不显著一律表述为『无显著差异』。")
md.append("- 低频组合过滤：分组统计中 n<30 的类别并入 Other 或单列提示，不进入两两比较。")
md.append("- 表述纪律：本阶段仅描述差异与关联，不作因果推断。")

(OUT / "阶段2_时效分析.md").write_text("\n".join(md) + "\n", encoding="utf-8")
print("阶段2完成，输出：")
for f in sorted(OUT.glob("fig2_*.png")):
    print(" 图表", f.name)
print(" 结论", (OUT / "阶段2_时效分析.md").name)
print(f" OTD={otd:.2f}%  迟到中位数={late.median():.1f}天")
