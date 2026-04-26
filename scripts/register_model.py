"""
Register an existing sklearn pipeline from training/model.pkl into MLflow registry.
Use when you trained without registration or need to re-publish the same artifact.

Typical flow is: run training/train.py (which registers automatically). This script is optional.
"""
from __future__ import annotations

import os
import pickle
import sys
from pathlib import Path

import mlflow
import mlflow.sklearn
from dotenv import load_dotenv
from mlflow.tracking import MlflowClient

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.example", override=False)

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000")
MLFLOW_MODEL_NAME = os.environ.get("MLFLOW_MODEL_NAME", "modelserve_classifier")
MODEL_PATH = Path(os.environ.get("MODEL_PATH", str(ROOT / "training" / "model.pkl")))


def main() -> None:
    if not MODEL_PATH.is_file():
        print(f"ERROR: no model at {MODEL_PATH}. Run training/train.py first.", file=sys.stderr)
        sys.exit(1)

    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    with mlflow.start_run(run_name="register_from_pkl") as run:
        run_id = run.info.run_id
        mlflow.sklearn.log_model(
            model,
            artifact_path="model",
            registered_model_name=MLFLOW_MODEL_NAME,
        )

    client = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
    versions = client.search_model_versions(f"name='{MLFLOW_MODEL_NAME}'")
    latest = max(versions, key=lambda v: int(v.version))
    client.transition_model_version_stage(
        MLFLOW_MODEL_NAME,
        str(latest.version),
        stage="Production",
        archive_existing_versions=True,
    )
    print(
        f"OK: registered {MLFLOW_MODEL_NAME} v{latest.version} -> Production (run {run_id})"
    )


if __name__ == "__main__":
    main()
