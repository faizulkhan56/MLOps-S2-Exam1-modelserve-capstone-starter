"""
Feast entities, FileSource, and FeatureView for fraud features.
Must match training/features.parquet (see training/feature_schema.py — keep column names in sync).

Apply from repo root:
  feast -c feast_repo apply
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from feast import Entity, FeatureView, Field, FileSource
from feast.types import Float64

FEAST_ROOT = Path(__file__).resolve().parent
ROOT = FEAST_ROOT.parent

# Keep in sync with training/feature_schema.py
ENTITY_ID_COL = "cc_num"
EVENT_TIMESTAMP_COL = "event_timestamp"
FEAST_NUMERIC_FEATURE_COLS = (
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

PARQUET_PATH = ROOT / "training" / "features.parquet"

cc_num_entity = Entity(
    name=ENTITY_ID_COL,
    join_keys=[ENTITY_ID_COL],
    description="Credit card number (Kaggle entity id)",
)

fraud_parquet = FileSource(
    name="fraud_parquet",
    path=str(PARQUET_PATH),
    timestamp_field=EVENT_TIMESTAMP_COL,
)

_schema = [Field(name=name, dtype=Float64) for name in FEAST_NUMERIC_FEATURE_COLS]

fraud_txn_features = FeatureView(
    name="fraud_txn_features",
    entities=[cc_num_entity],
    ttl=timedelta(days=365 * 5),
    schema=_schema,
    online=True,
    source=fraud_parquet,
    tags={"team": "modelserve"},
)
