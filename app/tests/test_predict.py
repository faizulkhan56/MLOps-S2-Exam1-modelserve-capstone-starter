# ============================================================================
# ModelServe — Tests
# ============================================================================
# TODO: Write tests for the inference service.
#
# Required tests:
#   - /health returns 200 with status and model_version fields
#   - /predict returns a valid prediction response for a known entity
#   - /predict returns 400 or 422 for invalid input
#   - /metrics returns 200 with Prometheus-format text
#   - At least one test that mocks the MLflow model and verifies prediction logic
#
# Testing tools:
#   - Use FastAPI's TestClient (from fastapi.testclient import TestClient)
#   - Use unittest.mock to mock MLflow and Feast dependencies
#   - Use pytest as the test runner
#
# These tests must pass in GitHub Actions CI.
# The TA will also run them during the demo.
# ============================================================================
