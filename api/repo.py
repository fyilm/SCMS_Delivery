"""数据访问层（Repository 模式）：以 scms_api 只读账号查询 ADS/DIM，与 FastAPI 解耦便于测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dw"))

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

    def kpis(self):
        return self._query("SELECT kpi, kpi_value, kpi_note FROM ads.v_otd_summary", ())

    def abc_summary(self):
        return self._query(
            "SELECT abc, vendor_cnt, line_cnt, total_value, value_pct "
            "FROM ads.v_abc_summary ORDER BY abc", ())

    def otd_by_mode(self):
        return self._query(
            "SELECT shipment_mode, line_cnt, ot_cnt, otd_pct, avg_delay, median_delay, p95_delay "
            "FROM dws.v_otd_by_mode ORDER BY otd_pct DESC", ())

    def otd_by_country(self):
        return self._query(
            "SELECT country, line_cnt, ot_cnt, otd_pct, median_delay "
            "FROM dws.v_otd_by_country ORDER BY otd_pct DESC", ())

    def cycle_summary(self):
        return self._query(
            "SELECT cycle_seg, seg_desc, sample_cnt, median_days, p95_days "
            "FROM dws.v_cycle_summary", ())

    def freight_by_mode(self):
        return self._query(
            "SELECT shipment_mode, sample_cnt, median_freight, p90_freight "
            "FROM dws.v_unit_freight_by_mode ORDER BY median_freight DESC", ())

    def monthly_summary(self):
        return self._query(
            "SELECT `year_month`, line_cnt, ot_cnt, otd_pct, total_value "
            "FROM dws.v_monthly_summary ORDER BY `year_month`", ())

    def _query(self, sql, args):
        from db import connect  # 懒加载，避免 pymysql/dotenv 拖慢服务启动

        conn = connect("api")
        try:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]
        finally:
            conn.close()
