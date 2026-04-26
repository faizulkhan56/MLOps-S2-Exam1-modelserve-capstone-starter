"""
Train a baseline fraud classifier, log to MLflow, register in Model Registry (Production),
export training/features.parquet and training/sample_request.json.

Prerequisites:
  - docker compose up -d postgres redis mlflow
  - data/raw/fraudTrain.csv (Kaggle) — or set FRAUD_TRAIN_PATH
  - python -m venv .venv && pip install -r requirements.txt
"""
from __future__ import annotations

import json
import os
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient

# Repo root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from training.feature_schema import (  # noqa: E402
    ENTITY_ID_COL,
    EVENT_TIMESTAMP_COL,
    FEAST_NUMERIC_FEATURE_COLS,
    RAW_TIMESTAMP_COL,
    TARGET_COL,
)

# Optional: .env in repo root
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.example", override=False)

RANDOM_STATE = 42
MLFLOW_EXPERIMENT_NAME = os.environ.get("MLFLOW_EXPERIMENT_NAME", "modelserve_fraud")
# Host uses localhost; override if needed (e.g. http://mlflow:5000 is for containers)
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000")
MLFLOW_MODEL_NAME = os.environ.get("MLFLOW_MODEL_NAME", "modelserve_classifier")
FRAUD_TRAIN_PATH = os.environ.get("FRAUD_TRAIN_PATH", str(ROOT / "data" / "raw" / "fraudTrain.csv"))
MODEL_PKL = ROOT / "training" / "model.pkl"
PARQUET_OUT = ROOT / "training" / "features.parquet"
SAMPLE_REQUEST = ROOT / "training" / "sample_request.json"


def _nrows() -> int | None:
    raw = os.environ.get("TRAIN_MAX_ROWS", "").strip()
    if not raw:
        return None
    return int(raw)


def load_raw(path: Path) -> pd.DataFrame:
    if not path.is_file():
        print(
            f"ERROR: training data not found: {path}\n"
            "Download: https://www.kaggle.com/datasets/kartik2112/fraud-detection\n"
            "Save fraudTrain.csv as data/raw/fraudTrain.csv or set FRAUD_TRAIN_PATH.",
            file=sys.stderr,
        )
        sys.exit(1)
    nrows = _nrows()
    return pd.read_csv(path, nrows=nrows)


def main() -> None:
    print(f"MLflow tracking URI: {MLFLOW_TRACKING_URI}")
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

    raw_path = Path(FRAUD_TRAIN_PATH)
    df = load_raw(raw_path)
    for c in (ENTITY_ID_COL, TARGET_COL, RAW_TIMESTAMP_COL):
        if c not in df.columns:
            print(f"ERROR: missing column {c!r} in {raw_path.name}", file=sys.stderr)
            sys.exit(1)

    df[EVENT_TIMESTAMP_COL] = pd.to_datetime(df[RAW_TIMESTAMP_COL], utc=True, errors="coerce")
    if df[EVENT_TIMESTAMP_COL].isna().all():
        raise SystemExit("Could not parse " + RAW_TIMESTAMP_COL)

    g = df.get("gender", pd.Series("U", index=df.index))
    df["gender_code"] = g.map({"M": 1.0, "F": 0.0}).fillna(0.0)
    df["zip"] = pd.to_numeric(df.get("zip", 0), errors="coerce").fillna(0.0)

    for c in [
        "amt",
        "lat",
        "long",
        "city_pop",
        "merch_lat",
        "merch_long",
        "unix_time",
    ]:
        if c not in df.columns:
            print(f"ERROR: missing column {c!r}", file=sys.stderr)
            sys.exit(1)
        df[c] = pd.to_numeric(df[c], errors="coerce")

    y = df[TARGET_COL].astype(int)
    good = (y == 0) | (y == 1)
    df, y = df.loc[good].reset_index(drop=True), y[good].to_numpy()

    num_cols = [
        c
        for c in [
            "amt",
            "lat",
            "long",
            "city_pop",
            "merch_lat",
            "merch_long",
            "unix_time",
            "zip",
            "gender_code",
        ]
        if c in df.columns
    ]
    cat_cols = [c for c in ("category", "state", "gender") if c in df.columns]
    for c in num_cols:
        df[c] = df[c].fillna(0.0)
    for c in cat_cols:
        df[c] = df[c].fillna("unk").astype(str)

    for c in FEAST_NUMERIC_FEATURE_COLS:
        if c not in df.columns:
            print(f"ERROR: need column {c!r} for Feast export", file=sys.stderr)
            sys.exit(1)

    export = df[[ENTITY_ID_COL, EVENT_TIMESTAMP_COL, *FEAST_NUMERIC_FEATURE_COLS]].copy()
    for c in FEAST_NUMERIC_FEATURE_COLS:
        export[c] = export[c].fillna(0.0)
    export[ENTITY_ID_COL] = export[ENTITY_ID_COL].astype("int64")

    if len(y) < 200:
        print("Not enough rows after filter.", file=sys.stderr)
        sys.exit(1)

    X = df[num_cols + cat_cols]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
    )

    pre = ColumnTransformer(
        [
            (
                "num",
                Pipeline(
                    [("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]
                ),
                num_cols,
            ),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False, max_categories=20),
                cat_cols,
            ),
        ],
        remainder="drop",
    )
    pipeline = Pipeline(
        [
            ("prep", pre),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=100,
                    max_depth=20,
                    min_samples_leaf=2,
                    class_weight="balanced",
                    n_jobs=-1,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )

    with mlflow.start_run(
        run_name=f"train_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    ) as run:
        run_id = run.info.run_id
        pipeline.fit(X_train, y_train)
        pred = pipeline.predict(X_test)
        proba = pipeline.predict_proba(X_test)[:, 1] if len(np.unique(y)) > 1 else pred

        m = {
            "accuracy": float(accuracy_score(y_test, pred)),
            "precision": float(precision_score(y_test, pred, zero_division=0)),
            "recall": float(recall_score(y_test, pred, zero_division=0)),
            "f1": float(f1_score(y_test, pred, zero_division=0)),
        }
        if len(np.unique(y_test)) > 1 and len(np.unique(pred)) > 1:
            m["roc_auc"] = float(roc_auc_score(y_test, proba))
        for k, v in m.items():
            mlflow.log_metric(k, v)
        mlflow.log_param("model", "RandomForestClassifier")
        mlflow.log_param("train_rows", int(len(X_train)))
        mlflow.log_param("n_features_raw", int(X_train.shape[1]))
        mlflow.log_param("data_path", str(raw_path))

        mlflow.sklearn.log_model(
            pipeline,
            artifact_path="model",
            registered_model_name=MLFLOW_MODEL_NAME,
        )

    client = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
    versions = client.search_model_versions(f"name='{MLFLOW_MODEL_NAME}'")
    if not versions:
        print("No model versions in registry; training run may have failed to register.", file=sys.stderr)
        sys.exit(1)
    latest = max(versions, key=lambda v: int(v.version))
    model_version = int(latest.version)
    client.transition_model_version_stage(
        MLFLOW_MODEL_NAME,
        str(model_version),
        stage="Production",
        archive_existing_versions=True,
    )
    print(
        f"OK: {MLFLOW_MODEL_NAME} v{model_version} -> Production (run {run_id})"
    )

    with open(MODEL_PKL, "wb") as f:
        pickle.dump(pipeline, f)
    print(f"Wrote {MODEL_PKL}")

    export.to_parquet(PARQUET_OUT, index=False, engine="pyarrow")
    print(f"Wrote {PARQUET_OUT} shape={export.shape}")

    rng = np.random.default_rng(RANDOM_STATE)
    pick = int(rng.choice(export[ENTITY_ID_COL].dropna().unique(), size=1)[0])
    with open(SAMPLE_REQUEST, "w", encoding="utf-8") as f:
        json.dump({"entity_id": pick}, f, indent=2)
    print(f"Wrote {SAMPLE_REQUEST} entity_id={pick}")


if __name__ == "__main__":
    main()
