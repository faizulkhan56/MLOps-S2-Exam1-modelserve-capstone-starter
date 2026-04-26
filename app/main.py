"""
ModelServe — FastAPI (Phases 1–2: health + metrics only).

Later phases will add MLflow + Feast + full /predict and explain routes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest, Info

APP_START_TIME = datetime.now(timezone.utc).isoformat()

# Minimal metrics so Prometheus has something to scrape before Phase 5 wiring.
PREDICTION_REQUESTS = Counter(
    "prediction_requests_total",
    "Total prediction requests (bootstrap counter).",
)
APP_INFO = Info("modelserve_bootstrap", "Bootstrap info for the API process.")
APP_INFO.info(
    {
        "phase": "1-2",
        "app_start_time": APP_START_TIME,
    }
)

app = FastAPI(
    title="ModelServe",
    version="0.1.0",
    description="MLOps S2 capstone — local stack bootstrap",
)


@app.get("/health")
def health() -> dict:
    """Liveness: stack is up; model not yet loaded from MLflow (Phases 3+)."""
    return {
        "status": "healthy",
        "model_version": "not_loaded",
    }


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


