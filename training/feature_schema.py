"""
Shared column names and feature list for training, Parquet export, and Feast.
Keep this file aligned with Kaggle: kartik2112/fraud-detection (fraudTrain.csv).
"""
from __future__ import annotations

# Raw CSV (Kaggle)
RAW_TIMESTAMP_COL = "trans_date_trans_time"
ENTITY_ID_COL = "cc_num"
TARGET_COL = "is_fraud"

# Parquet + Feast (same names the API and Offline store use)
EVENT_TIMESTAMP_COL = "event_timestamp"

# Model / Feast feature columns (numeric; match train.py preprocessing)
# Order is stable for tests and for Feast schema.
FEAST_NUMERIC_FEATURE_COLS: tuple[str, ...] = (
    "amt",
    "lat",
    "long",
    "city_pop",
    "merch_lat",
    "merch_long",
    "unix_time",
    "zip",
    "gender_code",
)
