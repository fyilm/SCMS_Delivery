"""口径对账：SQL(ADS/DWS) vs pandas 黄金数字，防止两套口径漂移。

运行：uv run python dw/analytics/reconcile.py
产出：output/对账报告.md；存在失败则退出码 1。
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "dw"))
from common import load_cleaned  # noqa: E402  (研究层 pandas 加载器)
from db import connect  # noqa: E402

REPORT = ROOT / "output" / "对账报告.md"


def pandas_goldens():
    df = load_cleaned()
    df["late_delay"] = df["delay_days"].where(df["delay_days"] > 0)

    g = {
        "total_lines": len(df),
        "otd_pct": 100 * df["ot_bool"].mean(),
        "late_cnt": int((df["delay_days"] > 0).sum()),
        "median_late": df.loc[df["delay_days"] > 0, "delay_days"].median(),
        "p99_late": df.loc[df["delay_days"] > 0, "delay_days"].quantile(0.99),
        "cycle": {
            "c1": df["c1_pq2po"].median(),
            "c2": df["c2_po2sched"].median(),
            "c3": df["c3_sched2deliv"].median(),
            "total": df["c_total"].median(),
        },
    }

    # 供应商评分卡（复刻 scripts/04_supplier.py）
    ven = df.groupby("Vendor").agg(
        lines=("ID", "size"), asn=("ASN/DN #", "nunique"),
        otd=("ot_bool", lambda s: 100 * s.mean()),
        avg_late=("late_delay", "mean"), late_n=("late_delay", "count"),
        value=("line_value", "sum"),
    ).reset_index()
    ven["avg_late"] = ven["avg_late"].fillna(0)
    scored = ven[ven["lines"] >= 10].copy()

    def norm_neg(s):
        r = s.max() - s.min()
        return 100.0 if r <= 0 else (s.max() - s) / r * 100

    def norm_pos(s):
        r = s.max() - s.min()
        return 100.0 if r <= 0 else (s - s.min()) / r * 100

    scored["s_otd"] = scored["otd"]
    scored["s_delay"] = norm_neg(scored["avg_late"])
    scored["s_value"] = norm_pos(scored["value"])
    scored["s_freq"] = norm_pos(scored["lines"])
    scored["score"] = (0.40 * scored["s_otd"] + 0.30 * scored["s_delay"]
                       + 0.20 * scored["s_value"] + 0.10 * scored["s_freq"])
    scored = scored.sort_values("score", ascending=False).reset_index(drop=True)

    ven_abc = ven.sort_values("value", ascending=False)
    ven_abc["cum"] = ven_abc["value"].cumsum() / ven_abc["value"].sum()
    ven_abc["ABC"] = np.select([ven_abc["cum"] <= 0.70, ven_abc["cum"] <= 0.90],
                               ["A", "B"], default="C")
    abc = ven_abc.groupby("ABC")["Vendor"].count().to_dict()

    g["scorecard_top5"] = scored[["Vendor", "score"]].head(5).values.tolist()
    g["scored_cnt"] = len(scored)
    g["abc_cnt"] = abc
    return g


def sql_actuals():
    conn = connect("etl")
    cur = conn.cursor()
    out = {}
    cur.execute("SELECT kpi, kpi_value FROM ads.otd_summary")
    out["kpi"] = {k: float(v) for k, v in cur.fetchall()}
    cur.execute("SELECT cycle_seg, median_days FROM dws.cycle_summary")
    out["cycle"] = {k: float(v) for k, v in cur.fetchall()}
    cur.execute("SELECT vendor, score FROM ads.supplier_scorecard ORDER BY score_rank LIMIT 5")
    out["scorecard_top5"] = [[v, float(s)] for v, s in cur.fetchall()]
    cur.execute("SELECT COUNT(*) FROM ads.supplier_scorecard")
    out["scored_cnt"] = cur.fetchone()[0]
    cur.execute("SELECT abc, vendor_cnt FROM ads.abc_summary")
    out["abc_cnt"] = {k: int(v) for k, v in cur.fetchall()}
    cur.execute("SELECT COUNT(*) FROM dws.otd_by_mode")
    out["mode_rows"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM dws.otd_by_country")
    out["country_rows"] = cur.fetchone()[0]
    conn.close()
    return out


def main():
    g = pandas_goldens()
    s = sql_actuals()
    rows = []
    fails = 0

    def check(name, p, q, tol, fmt="{:.2f}"):
        nonlocal fails
        ok = abs(float(p) - float(q)) <= tol
        if not ok:
            fails += 1
        rows.append([name, fmt.format(p), fmt.format(q), "通过" if ok else "失败"])
        return ok

    check("总行数", g["total_lines"], s["kpi"]["total_lines"], 0, "{:.0f}")
    check("准时率 OTD%", g["otd_pct"], s["kpi"]["otd_pct"], 0.01)
    check("迟到行数", g["late_cnt"], s["kpi"]["late_cnt"], 0, "{:.0f}")
    check("迟到中位数", g["median_late"], s["kpi"]["median_late_days"], 0.01)
    check("迟到 P99", g["p99_late"], s["kpi"]["p99_late_days"], 0.5)
    for seg in ["c1", "c2", "c3", "total"]:
        check(f"周期 {seg} 中位", g["cycle"][seg], s["cycle"][seg], 0.01)
    check("入评供应商数", g["scored_cnt"], s["scored_cnt"], 0, "{:.0f}")
    for i, (pv, pq) in enumerate(g["scorecard_top5"]):
        sv = dict(s["scorecard_top5"])
        check(f"评分卡 Top{i+1} 综合分", pq, sv[pv], 0.5)
    for abc in ["A", "B", "C"]:
        check(f"ABC {abc} 供应商数", g["abc_cnt"].get(abc, 0), s["abc_cnt"].get(abc, 0), 0, "{:.0f}")
    # 行数断言：汇总层分组数应等于维度基数（运输方式 5、国家 43）
    check("DWS 运输方式分组数=5", s["mode_rows"], 5, 0, "{:.0f}")
    check("DWS 国家分组数=43", s["country_rows"], 43, 0, "{:.0f}")

    lines = [
        "# 口径对账报告（SQL vs pandas）",
        f"- 规则 {len(rows)} 条，通过 {len(rows)-fails}，失败 {fails}",
        "",
        "| 指标 | pandas | SQL | 结果 |",
        "|---|---|---|---|",
    ]
    lines += [f"| {n} | {p} | {q} | {r} |" for n, p, q, r in rows]
    lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    for n, p, q, r in rows:
        print(f"  [{'PASS' if r=='通过' else 'FAIL'}] {n}: pandas={p} sql={q}")
    print(f"\n对账完成：通过 {len(rows)-fails}/{len(rows)}")
    print(f"报告：{REPORT}")
    if fails:
        sys.exit(1)


if __name__ == "__main__":
    main()
