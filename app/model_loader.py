"""Load sklearn model from MLflow Model Registry once at startup."""

from __future__ import annotations

import logging
import os
from typing import Any

import mlflow
import pandas as pd
from mlflow.tracking import MlflowClient

logger = logging.getLogger(__name__)

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000")
MLFLOW_MODEL_NAME = os.environ.get("MLFLOW_MODEL_NAME", "modelserve_classifier")
MLFLOW_MODEL_STAGE = os.environ.get("MLFLOW_MODEL_STAGE", "Production")

_model: Any | None = None
_version: str | None = None
_load_error: str | None = None


def load_from_registry() -> None:
    """Load Production model from MLflow; safe to call once at startup."""
    global _model, _version, _load_error
    _model = None
    _version = None
    _load_error = None
    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        uri = f"models:/{MLFLOW_MODEL_NAME}/{MLFLOW_MODEL_STAGE}"
        _model = mlflow.sklearn.load_model(uri)
        client = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
        versions = client.get_latest_versions(MLFLOW_MODEL_NAME, stages=[MLFLOW_MODEL_STAGE])
        if not versions:
            raise RuntimeError(
                f"No {MLFLOW_MODEL_STAGE} version for {MLFLOW_MODEL_NAME!r} in registry."
            )
        _version = str(versions[0].version)
        logger.info("Loaded MLflow model %s stage=%s version=%s", MLFLOW_MODEL_NAME, MLFLOW_MODEL_STAGE, _version)
    except Exception as exc:  # noqa: BLE001 — surface any load failure without crashing process
        _load_error = str(exc)
        logger.exception("Failed to load MLflow model: %s", exc)


def is_ready() -> bool:
    return _model is not None and _version is not None


def load_error() -> str | None:
    return _load_error


def version_string() -> str | None:
    return _version


def configure_for_testing(model: Any, version: str = "test") -> None:
    """Point the app at a fake sklearn-like model (pytest only)."""
    global _model, _version, _load_error
    _model = model
    _version = version
    _load_error = None


def predict(df: pd.DataFrame) -> tuple[Any, Any]:
    """
    Run sklearn pipeline predict + predict_proba on a single-row DataFrame
    matching training column order (numeric + categorical).
    """
    if _model is None:
        raise RuntimeError("Model is not loaded")
    y_pred = _model.predict(df)
    if not hasattr(_model, "predict_proba"):
        raise RuntimeError("Loaded model has no predict_proba")
    proba = _model.predict_proba(df)
    return y_pred, proba
