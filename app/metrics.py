# ============================================================================
# ModelServe — Prometheus Metrics
# ============================================================================
# TODO: Define Prometheus metrics for the inference service.
#
# Required metrics (from exam document):
#   - prediction_requests_total (Counter)
#       Total number of prediction requests received
#
#   - prediction_duration_seconds (Histogram)
#       Time taken to process each prediction (feature fetch + model inference)
#
#   - prediction_errors_total (Counter)
#       Number of failed prediction requests
#
#   - model_version_info (Gauge with a "version" label)
#       Currently served model version — set once on startup
#
#   - feast_online_store_hits_total (Counter)
#       Successful feature lookups from Feast
#
#   - feast_online_store_misses_total (Counter)
#       Failed or empty feature lookups from Feast
#
# Use the prometheus_client library:
#   from prometheus_client import Counter, Histogram, Gauge
#
# To expose metrics at /metrics, use generate_latest() from prometheus_client
# and return it as a Starlette Response with the correct content type.
# ============================================================================
