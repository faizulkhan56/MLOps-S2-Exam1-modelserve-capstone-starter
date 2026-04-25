# ============================================================================
# ModelServe — Feast Feature Definitions
# ============================================================================
# TODO: Define your Feast entities, data sources, and feature views.
#
# You need to create:
#
#   1. Entity — the credit card number (cc_num) from the dataset
#      - This is the join key for feature lookups
#
#   2. FileSource (or S3 source) — points to your features.parquet file
#      - Must specify the timestamp_field for point-in-time joins
#
#   3. FeatureView — maps the entity to features from the data source
#      - List every feature with its data type (Float64, Int64, String, etc.)
#      - Set a TTL (time-to-live) for feature freshness
#
# The features defined here must match exactly what train.py exports
# to features.parquet and what the FastAPI service requests from Feast.
#
# After defining these, run:
#   cd feast_repo && feast apply
#   python scripts/materialize_features.py
#
# Refer to Feast documentation: https://docs.feast.dev/
# ============================================================================
