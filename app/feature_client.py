# ============================================================================
# ModelServe — Feast Feature Client
# ============================================================================
# TODO: Implement feature fetching from the Feast online store.
#
# This module should:
#   - Initialize a Feast FeatureStore client pointing at your feast_repo
#   - Provide a get_features(entity_id) method that:
#     1. Calls store.get_online_features() with the entity key (cc_num)
#     2. Converts the result to a dictionary or DataFrame
#     3. Handles missing features gracefully (log warning, return defaults)
#   - Track hit/miss counts for Prometheus metrics
#
# Key Feast APIs to use:
#   - feast.FeatureStore(repo_path=...)
#   - store.get_online_features(features=[...], entity_rows=[...])
#
# IMPORTANT: Use the Feast SDK — do NOT query Redis directly.
# The TA will check this during the demo.
# ============================================================================
