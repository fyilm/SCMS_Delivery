"""执行 SQL 分析层：物化 DWS/ADS（读取 refresh_ads.sql，以 scms_etl 执行，仅 DML）。

运行：uv run python dw/analytics/refresh_ads.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import connect  # noqa: E402

SQL_FILE = Path(__file__).parent / "sql" / "refresh_ads.sql"


def split_statements(sql: str):
    statements = []
    buf = []
    for line in sql.splitlines():
        s = line.strip()
        if s.startswith("--"):
            continue
        buf.append(line)
        if s.endswith(";"):
            stmt = "\n".join(buf).rstrip(";").strip()
            if stmt:
                statements.append(stmt)
            buf = []
    return statements


def main():
    sql = SQL_FILE.read_text(encoding="utf-8")
    conn = connect("etl")
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO ops.run_log (stage, status, message) VALUES ('refresh_ads','start','')")
            run_id = cur.lastrowid
        done = 0
        for stmt in split_statements(sql):
            with conn.cursor() as cur:
                cur.execute(stmt)
            done += 1
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("UPDATE ops.run_log SET status='success', rows_affected=%s, message=%s WHERE run_id=%s",
                        (done, f"执行 {done} 条 SQL", run_id))
        conn.commit()
        print(f"SQL 分析层物化完成：执行 {done} 条语句")
    except Exception as e:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("UPDATE ops.run_log SET status='fail', message=%s WHERE run_id=%s", (str(e), run_id))
        conn.commit()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
