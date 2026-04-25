# ============================================================================
# ModelServe — FastAPI Inference Service
# ============================================================================
# TODO: Implement the FastAPI application with the following endpoints:
#
#   GET  /health
#     - Returns: {"status": "healthy", "model_version": "<version>"}
#     - Used by Docker healthchecks and CI deploy verification
#
#   POST /predict
#     - Accepts: {"entity_id": <int>}
#     - Steps:
#       1. Fetch features from Feast online store using entity_id
#       2. Run the model (loaded on startup from MLflow Registry)
#       3. Record Prometheus metrics (request count, duration, errors)
#       4. Return: {"prediction": <int>, "probability": <float>,
#                   "model_version": "<version>", "timestamp": "<iso8601>"}
#
#   GET  /predict/<entity_id>?explain=true
#     - Same as POST /predict but also returns the feature values used
#     - Useful for debugging predictions during the demo
#
#   GET  /metrics
#     - Exposes Prometheus metrics in text format
#     - Must include: prediction_requests_total, prediction_duration_seconds,
#       prediction_errors_total, model_version_info
#
# Key design requirements:
#   - Load the model from MLflow Registry ONCE on startup (not per request)
#   - Fetch features through Feast SDK (not direct Redis queries)
#   - Return structured JSON errors with appropriate HTTP status codes
#   - Use Pydantic models for request/response validation
# ============================================================================
