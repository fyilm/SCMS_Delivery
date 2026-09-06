"""数据访问层（Repository 模式）：以 scms_api 只读账号查询 ADS/DIM，与 FastAPI 解耦便于测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dw"))
from db import connect  # noqa: E402

SCORE_COLS = ["score_rank", "vendor", "abc", "line_cnt", "asn_cnt",
              "otd", "avg_late", "late_cnt", "total_value", "score"]


class SupplierRepo:
    def list_suppliers(self, limit=20, otd_lt=None, abc=None):
        sql = "SELECT " + ", ".join(SCORE_COLS) + " FROM ads.supplier_scorecard"
        conds, args = [], []
        if otd_lt is not None:
            conds.append("otd < %s")
            args.append(otd_lt)
        if abc is not None:
            conds.append("abc = %s")
            args.append(abc)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY score_rank LIMIT %s"
        args.append(limit)
        return self._query(sql, args)

    def get_score(self, name: str):
        sql = ("SELECT " + ", ".join(SCORE_COLS)
               + " FROM ads.supplier_scorecard WHERE vendor = %s")
        rows = self._query(sql, (name,))
        return rows[0] if rows else None

    def _query(self, sql, args):
        conn = connect("api")
        try:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]
        finally:
            conn.close()
