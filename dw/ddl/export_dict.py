"""导出数据字典：从 meta.table_dict / meta.column_dict 生成 docs/数据字典.md（root 只读）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import connect  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "数据字典.md"


def main():
    conn = connect("root")
    cur = conn.cursor()
    cur.execute("SELECT schema_name, table_name, layer, table_comment FROM meta.table_dict ORDER BY schema_name, table_name")
    tables = cur.fetchall()
    cur.execute("SELECT schema_name, table_name, column_name, data_type, column_comment FROM meta.column_dict ORDER BY schema_name, table_name, column_name")
    cols = cur.fetchall()
    conn.close()

    lines = ["# 数据字典", "", f"- 共 {len(tables)} 张表", ""]
    for sch, tbl, layer, cmt in tables:
        lines.append(f"## {sch}.{tbl}")
        lines.append(f"- 分层：{layer}；说明：{cmt or '-'}")
        lines.append("")
        lines.append("| 列名 | 类型 | 说明 |")
        lines.append("|---|---|---|")
        for s, t, c, dt, cc in cols:
            if s == sch and t == tbl:
                lines.append(f"| `{c}` | {dt} | {cc or '-'} |")
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"数据字典已导出：{OUT}（{len(tables)} 表）")


if __name__ == "__main__":
    main()
