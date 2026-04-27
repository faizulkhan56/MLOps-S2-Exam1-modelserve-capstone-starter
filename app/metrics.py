"""Prometheus metrics for the inference service."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

prediction_requests_total = Counter(
    "prediction_requests_total",
    "Total POST /predict requests received.",
)

prediction_duration_seconds = Histogram(
    "prediction_duration_seconds",
    "Wall time for a prediction (Feast fetch + model inference).",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

prediction_errors_total = Counter(
    "prediction_errors_total",
    "Failed prediction requests.",
    labelnames=("reason",),
)

feast_online_store_hits_total = Counter(
    "feast_online_store_hits_total",
    "Successful Feast online feature lookups.",
)

feast_online_store_misses_total = Counter(
    "feast_online_store_misses_total",
    "Feast lookups with missing or unusable feature rows.",
    labelnames=("reason",),
)

model_version_info = Gauge(
    "model_version_info",
    "Currently served MLflow model (labels identify name and version).",
    labelnames=("model_name", "version"),
)


def set_served_model(model_name: str, version: str) -> None:
    """Expose one active series for the served model (value is always 1)."""
    model_version_info.labels(model_name=model_name, version=version).set(1)
