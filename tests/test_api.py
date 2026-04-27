"""API tests: health, validation, mocked predict."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.feature_client import FEAST_NUMERIC_FEATURE_COLS  # noqa: E402


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    """App with MLflow + Feast backed by fakes (no live stack)."""
    from app import model_loader

    def _fake_load() -> None:
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([1])
        mock_model.predict_proba.return_value = np.array([[0.25, 0.75]])
        model_loader.configure_for_testing(mock_model, version="42")

    class _FakeFeast:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def get_features(self, entity_id: int) -> dict[str, float]:
            return {name: float(i + 1) for i, name in enumerate(FEAST_NUMERIC_FEATURE_COLS)}

    monkeypatch.setattr("app.model_loader.load_from_registry", _fake_load)
    monkeypatch.setattr("app.feature_client.FeastFeatureClient", _FakeFeast)

    from app.main import app

    with TestClient(app) as c:
        yield c


def test_health_ok(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["model_version"] == "42"


def test_predict_invalid_body(client: TestClient) -> None:
    r = client.post("/predict", json={})
    assert r.status_code == 422


def test_predict_invalid_type(client: TestClient) -> None:
    r = client.post("/predict", json={"entity_id": "not-an-int"})
    assert r.status_code == 422


def test_predict_success_mocked(client: TestClient) -> None:
    r = client.post("/predict", json={"entity_id": 999001})
    assert r.status_code == 200
    data = r.json()
    assert data["entity_id"] == 999001
    assert data["prediction"] == 1
    assert data["fraud_probability"] == pytest.approx(0.75)
    assert data["model_name"] == "modelserve_classifier"
    assert data["model_version"] == "42"
    assert "timestamp" in data


def test_metrics_endpoint(client: TestClient) -> None:
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "prediction_requests_total" in r.text
