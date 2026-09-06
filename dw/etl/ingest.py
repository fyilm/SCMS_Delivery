"""ETL：原始 CSV → ODS(贴源) → DWD(明细) → DIM(维度)，全量幂等重建。

口径严格对齐 scripts/01_prepare.py 与 docs/口径文档.md v1.1。
运行：uv run python dw/etl/ingest.py
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import connect  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "SCMS_Delivery_History_data.csv"

# ---- 原始列 -> ODS 列映射 ----
ODS_COLS = [
    "id", "project_code", "pq_no", "po_so_no", "asn_dn_no", "country",
    "managed_by", "fulfill_via", "vendor_inco_term", "shipment_mode",
    "pq_date_raw", "po_date_raw", "scheduled_date_raw", "delivered_date_raw",
    "recorded_date_raw", "product_group", "sub_classification", "vendor",
    "item_description", "molecule_test_type", "brand", "dosage", "dosage_form",
    "uom_raw", "qty_raw", "line_value_raw", "pack_price_raw", "unit_price_raw",
    "manufacturing_site", "first_line_designation", "weight_raw",
    "freight_raw", "insurance_raw",
]
RAW_COLS = [
    "ID", "Project Code", "PQ #", "PO / SO #", "ASN/DN #", "Country",
    "Managed By", "Fulfill Via", "Vendor INCO Term", "Shipment Mode",
    "PQ First Sent to Client Date", "PO Sent to Vendor Date",
    "Scheduled Delivery Date", "Delivered to Client Date",
    "Delivery Recorded Date", "Product Group", "Sub Classification",
    "Vendor", "Item Description", "Molecule/Test Type", "Brand", "Dosage",
    "Dosage Form", "Unit of Measure (Per Pack)", "Line Item Quantity",
    "Line Item Value", "Pack Price", "Unit Price", "Manufacturing Site",
    "First Line Designation", "Weight (Kilograms)", "Freight Cost (USD)",
    "Line Item Insurance (USD)",
]

DWD_COLS = [
    "id", "project_code", "pq_no", "po_so_no", "asn_dn_no", "country",
    "managed_by", "fulfill_via", "vendor_inco_term", "shipment_mode",
    "pq_date", "po_date", "scheduled_date", "delivered_date", "recorded_date",
    "product_group", "sub_classification", "vendor", "item_description",
    "molecule_test_type", "brand", "dosage", "dosage_form", "uom", "qty",
    "line_value", "pack_price", "unit_price", "manufacturing_site",
    "first_line_designation", "weight_numeric", "freight_numeric", "insurance",
    "pq_flag", "po_flag", "freight_flag", "flag_weight_reference",
    "flag_zero_value", "flag_qty_outlier", "flag_line_value_outlier",
    "flag_pack_price_outlier", "flag_unit_price_outlier", "flag_weight_outlier",
    "flag_freight_outlier", "flag_insurance_outlier", "delay_days", "ot_bool",
    "early_bool", "c1_pq2po", "c2_po2sched", "c3_sched2deliv", "c_total",
    "flag_negative_cycle", "unit_freight", "flag_unit_freight_extreme",
    "delivery_year", "delivery_month",
]
DATE_COLS = ["pq_date", "po_date", "scheduled_date", "delivered_date", "recorded_date"]


def _conv(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return int(v)
    if v is pd.NaT:
        return None
    return v


def insert_df(conn, table, df, cols):
    if df is None or len(df) == 0:
        return 0
    df = df[cols].copy()
    for c in DATE_COLS:
        if c in df.columns:
            df[c] = df[c].apply(lambda x: x.date() if pd.notna(x) else None)
    placeholders = ", ".join(["%s"] * len(cols))
    col_sql = ", ".join(f"`{c}`" for c in cols)
    table_sql = ".".join(f"`{p}`" for p in table.split("."))
    sql = f"INSERT INTO {table_sql} ({col_sql}) VALUES ({placeholders})"
    rows = [tuple(_conv(v) for v in rec) for rec in df.itertuples(index=False)]
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    return len(rows)


def log_run(conn, stage, status, rows, message=""):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO ops.run_log (stage, status, rows_affected, message) VALUES (%s,%s,%s,%s)",
            (stage, status, rows, message),
        )


def load_ods(df):
    m = dict(zip(RAW_COLS, ODS_COLS))
    out = df[RAW_COLS].rename(columns=m).copy()
    for c in out.columns:
        out[c] = out[c].apply(lambda x: None if (isinstance(x, str) and x == "") else x)
    return out


def clean_to_dwd(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()

    # 日期解析（两套格式 + 业务状态）
    pq_raw = df["PQ First Sent to Client Date"].fillna("")
    po_raw = df["PO Sent to Vendor Date"].fillna("")
    pq_flag = pd.Series("date", index=df.index)
    pq_flag[pq_raw == "Pre-PQ Process"] = "pre_pq"
    pq_flag[pq_raw == "Date Not Captured"] = "not_captured"
    po_flag = pd.Series("date", index=df.index)
    po_flag[po_raw == "N/A - From RDC"] = "from_rdc"
    po_flag[po_raw == "Date Not Captured"] = "not_captured"

    def parse_dates(series, fmt):
        return pd.to_datetime(series, format=fmt, errors="coerce")

    pq = parse_dates(pq_raw.where(pq_flag == "date"), "%m/%d/%y")
    po = parse_dates(po_raw.where(po_flag == "date"), "%m/%d/%y")
    sch = parse_dates(df["Scheduled Delivery Date"], "%d-%b-%y")
    delv = parse_dates(df["Delivered to Client Date"], "%d-%b-%y")
    rec = parse_dates(df["Delivery Recorded Date"], "%d-%b-%y")

    # Freight 文本标记
    freight_raw = df["Freight Cost (USD)"].fillna("")
    freight_flag = pd.Series("numeric", index=df.index)
    freight_flag[freight_raw == "Freight Included in Commodity Cost"] = "included"
    freight_flag[freight_raw == "Invoiced Separately"] = "invoiced"
    freight_flag[freight_raw.str.startswith("See ", na=False)] = "reference"
    freight_numeric = pd.to_numeric(freight_raw.where(freight_flag == "numeric"), errors="coerce")

    # Weight 文本引用 + 分母保护
    weight_raw = df["Weight (Kilograms)"].fillna("")
    weight_text = weight_raw.str.startswith("See ", na=False) & weight_raw.ne("")
    weight_numeric = pd.to_numeric(weight_raw, errors="coerce")
    weight_numeric[weight_numeric <= 0] = np.nan

    # 数值列
    qty = pd.to_numeric(df["Line Item Quantity"], errors="coerce")
    line_value = pd.to_numeric(df["Line Item Value"], errors="coerce")
    pack_price = pd.to_numeric(df["Pack Price"], errors="coerce")
    unit_price = pd.to_numeric(df["Unit Price"], errors="coerce")
    insurance = pd.to_numeric(df["Line Item Insurance (USD)"], errors="coerce")
    uom = pd.to_numeric(df["Unit of Measure (Per Pack)"], errors="coerce")

    # 特征工程
    out = pd.DataFrame()
    m = dict(zip(RAW_COLS, ODS_COLS))
    out["id"] = df["ID"].astype(int)
    out["project_code"] = df["Project Code"]
    out["pq_no"] = df["PQ #"]
    out["po_so_no"] = df["PO / SO #"]
    out["asn_dn_no"] = df["ASN/DN #"]
    out["country"] = df["Country"]
    out["managed_by"] = df["Managed By"]
    out["fulfill_via"] = df["Fulfill Via"]
    out["vendor_inco_term"] = df["Vendor INCO Term"]
    out["shipment_mode"] = df["Shipment Mode"]
    out["pq_date"] = pq
    out["po_date"] = po
    out["scheduled_date"] = sch
    out["delivered_date"] = delv
    out["recorded_date"] = rec
    out["product_group"] = df["Product Group"]
    out["sub_classification"] = df["Sub Classification"]
    out["vendor"] = df["Vendor"]
    out["item_description"] = df["Item Description"]
    out["molecule_test_type"] = df["Molecule/Test Type"]
    out["brand"] = df["Brand"]
    out["dosage"] = df["Dosage"]
    out["dosage_form"] = df["Dosage Form"]
    out["uom"] = uom
    out["qty"] = qty
    out["line_value"] = line_value
    out["pack_price"] = pack_price
    out["unit_price"] = unit_price
    out["manufacturing_site"] = df["Manufacturing Site"]
    out["first_line_designation"] = df["First Line Designation"]
    out["weight_numeric"] = weight_numeric
    out["freight_numeric"] = freight_numeric
    out["insurance"] = insurance
    out["pq_flag"] = pq_flag
    out["po_flag"] = po_flag
    out["freight_flag"] = freight_flag
    out["flag_weight_reference"] = weight_text.astype(int)
    out["flag_zero_value"] = (line_value == 0).astype(int)

    outlier_cols = {
        "flag_qty_outlier": qty, "flag_line_value_outlier": line_value,
        "flag_pack_price_outlier": pack_price, "flag_unit_price_outlier": unit_price,
        "flag_weight_outlier": weight_numeric, "flag_freight_outlier": freight_numeric,
        "flag_insurance_outlier": insurance,
    }
    for flag, s in outlier_cols.items():
        lo, hi = s.quantile(0.25), s.quantile(0.75)
        iqr = hi - lo
        out[flag] = ((s < lo - 1.5 * iqr) | (s > hi + 1.5 * iqr)).astype(int)

    out["delay_days"] = (delv - sch).dt.days
    out["ot_bool"] = (out["delay_days"] <= 0).astype(int).where(out["delay_days"].notna())
    out["early_bool"] = (out["delay_days"] < 0).astype(int).where(out["delay_days"].notna())
    out["c1_pq2po"] = (po - pq).dt.days
    out["c2_po2sched"] = (sch - po).dt.days
    out["c3_sched2deliv"] = (delv - sch).dt.days
    out["c_total"] = (delv - pq).dt.days
    neg_cycle = (out["c1_pq2po"] < 0) | (out["c2_po2sched"] < 0) | (out["c_total"] < 0)
    out["flag_negative_cycle"] = neg_cycle.astype(int).where(neg_cycle.notna())
    out["unit_freight"] = freight_numeric / weight_numeric
    out["flag_unit_freight_extreme"] = (out["unit_freight"] > 10000).astype(int).where(out["unit_freight"].notna())
    out["delivery_year"] = delv.dt.year
    out["delivery_month"] = delv.dt.to_period("M").astype(str).where(delv.notna())

    # 布尔列 NaN 处理（fillna 0 仅针对非业务 flag）
    for c in ["flag_weight_reference", "flag_zero_value", "flag_qty_outlier",
              "flag_line_value_outlier", "flag_pack_price_outlier",
              "flag_unit_price_outlier", "flag_weight_outlier",
              "flag_freight_outlier", "flag_insurance_outlier"]:
        out[c] = out[c].fillna(0).astype(int)
    for c in ["flag_negative_cycle", "flag_unit_freight_extreme"]:
        out[c] = out[c].fillna(0).astype(int)
    out["ot_bool"] = out["ot_bool"].astype("Int64")
    out["early_bool"] = out["early_bool"].astype("Int64")
    return out


def build_dims(dwd: pd.DataFrame):
    ven = dwd.groupby("vendor").agg(
        line_cnt=("id", "size"),
        asn_cnt=("asn_dn_no", "nunique"),
        first_date=("delivered_date", "min"),
        last_date=("delivered_date", "max"),
    ).reset_index()
    cty = dwd.groupby("country").agg(
        line_cnt=("id", "size"),
        vendor_cnt=("vendor", "nunique"),
    ).reset_index()
    pg = dwd.groupby(["product_group", "sub_classification"]).agg(
        line_cnt=("id", "size"),
    ).reset_index()
    dmin = dwd["delivered_date"].min()
    dmax = dwd["delivered_date"].max()
    dates = pd.date_range(dmin, dmax)
    dd = pd.DataFrame({
        "cal_date": dates.date,
        "cal_year": dates.year,
        "cal_month": dates.month,
        "year_month": dates.strftime("%Y-%m"),
        "cal_quarter": dates.quarter,
    })
    return ven, cty, pg, dd


def main():
    raw = pd.read_csv(RAW, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
    n_raw = len(raw)
    raw = raw.drop_duplicates().reset_index(drop=True)
    if raw["ID"].duplicated().any():
        raw = raw.drop_duplicates(subset=["ID"], keep="first").reset_index(drop=True)

    ods = load_ods(raw)
    dwd = clean_to_dwd(raw)
    ven, cty, pg, dd = build_dims(dwd)

    conn = connect("etl")
    try:
        with conn.cursor() as cur:
            for tbl in ["ods.raw_shipment", "dwd.fact_shipment", "dim.dim_vendor",
                        "dim.dim_country", "dim.dim_product_group", "dim.dim_date"]:
                cur.execute(f"DELETE FROM {tbl}")
        log_run(conn, "ingest", "start", 0, f"raw={n_raw} dedup={len(raw)}")

        n_ods = insert_df(conn, "ods.raw_shipment", ods, ODS_COLS)
        n_dwd = insert_df(conn, "dwd.fact_shipment", dwd, DWD_COLS)
        n_ven = insert_df(conn, "dim.dim_vendor", ven, ven.columns.tolist())
        n_cty = insert_df(conn, "dim.dim_country", cty, cty.columns.tolist())
        n_pg = insert_df(conn, "dim.dim_product_group", pg, pg.columns.tolist())
        n_dd = insert_df(conn, "dim.dim_date", dd, dd.columns.tolist())

        conn.commit()
        log_run(conn, "ingest", "success", n_dwd,
                f"ods={n_ods} dwd={n_dwd} dim_vendor={n_ven} dim_country={n_cty} "
                f"dim_product={n_pg} dim_date={n_dd}")
        print(f"ETL 完成：原始 {n_raw} -> 去重 {len(raw)} 行")
        print(f"  ODS raw_shipment={n_ods}, DWD fact_shipment={n_dwd}")
        print(f"  DIM vendor={n_ven} country={n_cty} product={n_pg} date={n_dd}")
    except Exception as e:
        conn.rollback()
        log_run(conn, "ingest", "fail", 0, str(e))
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
