"""共享工具：清洗后数据集的标准加载器。

关键点：pandas 默认把字面量 "N/A" 当作缺失值，但本数据里 Shipment Mode /
Dosage 等字段的 "N/A" 是合法的业务类别，故必须 keep_default_na=False。
"""
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLEANED = ROOT / "output" / "scms_cleaned.csv"

DATE_COLS = ["pq_date", "po_date", "scheduled_date", "delivered_date", "recorded_date"]


def load_cleaned():
    df = pd.read_csv(CLEANED, encoding="utf-8-sig", keep_default_na=False,
                     na_values=[""], low_memory=False)
    for c in DATE_COLS:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    return df
