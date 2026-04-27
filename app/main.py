"""
ModelServe — FastAPI inference (Phase 5): MLflow + Feast + Prometheus.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from app import metrics, model_loader
from app.feature_client import FeastFeatureClient, FEAST_NUMERIC_FEATURE_COLS

logger = logging.getLogger(__name__)

MLFLOW_MODEL_NAME = os.environ.get("MLFLOW_MODEL_NAME", "modelserve_classifier")

# Training uses raw categoricals + numerics; Feast only serves numerics — defaults match train fillna.
_CAT_DEFAULTS = {"category": "unk", "state": "unk", "gender": "unk"}
_CAT_ORDER = ("category", "state", "gender")

_feast_client: FeastFeatureClient | None = None
_feast_init_error: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _feast_client, _feast_init_error
    model_loader.load_from_registry()
    if model_loader.is_ready():
        metrics.set_served_model(MLFLOW_MODEL_NAME, model_loader.version_string() or "unknown")
    _feast_client = None
    _feast_init_error = None
    try:
        _feast_client = FeastFeatureClient()
    except Exception as exc:  # noqa: BLE001
        _feast_init_error = str(exc)
        logger.exception("Feast FeatureStore init failed: %s", exc)
    yield


app = FastAPI(
    title="ModelServe",
    version="0.2.0",
    description="MLOps S2 capstone — MLflow + Feast inference",
    lifespan=lifespan,
)


class PredictRequest(BaseModel):
    entity_id: int = Field(..., description="Feast entity key (cc_num)")


def _error_body(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def _build_model_frame(feature_dict: dict[str, float]) -> pd.DataFrame:
    row: dict[str, Any] = dict(feature_dict)
    row.update(_CAT_DEFAULTS)
    num_cols = list(FEAST_NUMERIC_FEATURE_COLS)
    ordered = num_cols + list(_CAT_ORDER)
    return pd.DataFrame([{c: row[c] for c in ordered}], columns=ordered)


@app.get("/health")
def health() -> dict[str, Any]:
    if not model_loader.is_ready():
        return {
            "status": "degraded",
            "model_version": "not_loaded",
            "detail": model_loader.load_error(),
        }
    out: dict[str, Any] = {
        "status": "healthy",
        "model_version": model_loader.version_string(),
    }
    if _feast_init_error:
        out["feast"] = "degraded"
        out["feast_detail"] = _feast_init_error
    return out


@app.get("/metrics")
def prometheus_metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/predict")
def predict(req: PredictRequest) -> dict[str, Any]:
    metrics.prediction_requests_total.inc()
    if not model_loader.is_ready():
        metrics.prediction_errors_total.labels(reason="model_unavailable").inc()
        return _error_body(
            "model_unavailable",
            model_loader.load_error() or "Model is not loaded",
            503,
        )
    if _feast_client is None:
        metrics.prediction_errors_total.labels(reason="feast_unavailable").inc()
        return _error_body(
            "feast_unavailable",
            _feast_init_error or "Feast client is not initialized",
            503,
        )

    t0 = time.perf_counter()
    try:
        feats = _feast_client.get_features(req.entity_id)
    except ValueError as exc:
        metrics.prediction_errors_total.labels(reason="missing_features").inc()
        metrics.prediction_duration_seconds.observe(time.perf_counter() - t0)
        return _error_body("missing_features", str(exc), 404)

    try:
        X = _build_model_frame(feats)
        y_pred, proba = model_loader.predict(X)
        fraud_probability = float(proba[0][1])
        prediction = int(y_pred[0])
    except RuntimeError as exc:
        metrics.prediction_errors_total.labels(reason="inference").inc()
        metrics.prediction_duration_seconds.observe(time.perf_counter() - t0)
        return _error_body("inference_error", str(exc), 500)
    except Exception as exc:  # noqa: BLE001
        logger.exception("predict failed: %s", exc)
        metrics.prediction_errors_total.labels(reason="internal").inc()
        metrics.prediction_duration_seconds.observe(time.perf_counter() - t0)
        return _error_body("internal_error", "Unexpected error during prediction", 500)

    metrics.prediction_duration_seconds.observe(time.perf_counter() - t0)
    return {
        "entity_id": int(req.entity_id),
        "prediction": prediction,
        "fraud_probability": fraud_probability,
        "model_name": MLFLOW_MODEL_NAME,
        "model_version": model_loader.version_string(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
