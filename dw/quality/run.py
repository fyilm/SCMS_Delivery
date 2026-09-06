"""数据质量巡检：执行 rules.yaml → 写 ops.dq_run_result / ops.dq_alert → 生成巡检报告。

运行：uv run python dw/quality/run.py
退出码：存在 fatal 失败时为 1（供调度/CI 判定）。
"""
import operator
import sys
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import connect  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RULES_YAML = Path(__file__).parent / "rules.yaml"
REPORT_PATH = ROOT / "output" / "巡检报告.md"

OPS = {
    "eq": operator.eq, "ne": operator.ne, "gt": operator.gt,
    "lt": operator.lt, "ge": operator.ge, "le": operator.le,
}


def to_num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def main():
    rules = yaml.safe_load(RULES_YAML.read_text(encoding="utf-8"))
    conn = connect("etl")
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO ops.run_log (stage, status, message) VALUES ('quality','start','')")
            run_id = cur.lastrowid

        results = []
        fatal_fail = 0
        for r in rules:
            with conn.cursor() as cur:
                cur.execute(r["query"])
                actual = cur.fetchone()[0]
            ok = OPS[r["op"]](to_num(actual), to_num(r["expected"]))
            status = "pass" if ok else "fail"
            if not ok and r["level"] == "fatal":
                fatal_fail += 1
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO ops.dq_run_result (run_id, rule_id, dimension, level, status, actual, expected, message) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (run_id, r["id"], r["dimension"], r["level"], status,
                     str(actual), str(r["expected"]), r["name"]),
                )
                if not ok and r["level"] == "fatal":
                    cur.execute(
                        "INSERT INTO ops.dq_alert (run_id, rule_id, level, message) VALUES (%s,%s,%s,%s)",
                        (run_id, r["id"], "fatal", f"[{r['id']}] {r['name']}: actual={actual}, expected={r['expected']}"),
                    )
            results.append({**r, "actual": actual, "status": status})

        # ADS 质量汇总（按层 × 维度）
        agg = {}
        for r in results:
            key = (r["layer"], r["dimension"])
            a = agg.setdefault(key, {"total": 0, "fail": 0})
            a["total"] += 1
            a["fail"] += 1 if r["status"] == "fail" else 0
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ads.quality_summary")
            for (layer, dim), a in agg.items():
                rate = round(100 * (a["total"] - a["fail"]) / a["total"], 2)
                cur.execute(
                    "INSERT INTO ads.quality_summary (layer, dimension, total_cnt, fail_cnt, pass_rate) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (layer, dim, a["total"], a["fail"], rate),
                )

        conn.commit()
        with conn.cursor() as cur:
            cur.execute("UPDATE ops.run_log SET status=%s, message=%s WHERE run_id=%s",
                        ("fail" if fatal_fail else "success",
                         f"规则{len(rules)}条, fatal失败{fatal_fail}条", run_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    write_report(rules, results, run_id, fatal_fail)

    for r in results:
        mark = "PASS" if r["status"] == "pass" else "FAIL"
        print(f"  [{mark}] {r['dimension']}/{r['level']} {r['name']}: actual={r['actual']}")
    print(f"\n质检完成：共 {len(results)} 条规则，失败 {sum(1 for r in results if r['status']=='fail')} 条，fatal 失败 {fatal_fail} 条")
    print(f"巡检报告：{REPORT_PATH}")
    if fatal_fail:
        sys.exit(1)


def write_report(rules, results, run_id, fatal_fail):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fail = [r for r in results if r["status"] == "fail"]
    layer_fail = {}
    for r in fail:
        layer_fail[r["layer"]] = layer_fail.get(r["layer"], 0) + 1

    dim_order = ["完整性", "有效性", "一致性", "及时性"]
    lines = [
        f"# 数据质量巡检报告",
        f"- 生成时间：{ts}；运行 ID：{run_id}",
        f"- 规则总数：{len(results)}；通过：{len(results) - len(fail)}；失败：{len(fail)}；fatal 失败：{fatal_fail}",
        "",
        "## 各层问题占比",
        "| 分层 | 失败规则数 | 占失败总数比例 |",
        "|---|---|---|",
    ]
    total_fail = len(fail) or 1
    for layer in sorted(layer_fail, key=lambda x: -layer_fail[x]):
        lines.append(f"| {layer} | {layer_fail[layer]} | {layer_fail[layer] / total_fail * 100:.1f}% |")
    if not layer_fail:
        lines.append("| — | 0 | 0% |")
    lines += ["", "## 规则明细", "| ID | 维度 | 级别 | 分层 | 规则 | 结果 | 实际 | 期望 |",
              "|---|---|---|---|---|---|---|---|"]
    for r in results:
        mark = "通过" if r["status"] == "pass" else "失败"
        lines.append(f"| {r['id']} | {r['dimension']} | {r['level']} | {r['layer']} | {r['name']} | {mark} | {r['actual']} | {r['expected']} |")
    lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
