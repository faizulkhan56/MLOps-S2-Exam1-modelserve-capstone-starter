# Line-by-line explanation: training, Feast, MLflow & API

> **Purpose:** Walk through how `training/train.py` and `app/main.py` fit together, with **extra “demo” notes** for a viva or live walkthrough.  
> **Source:** Based on `explanation-linewise.txt` in this directory, **restructured, completed** (the `.txt` cut off mid-sentence at the end), and **expanded** where it helps the demo.  
> **Out of scope here:** `infrastructure/`, `monitoring/` implementation detail, `tests/`, GitHub Actions — see [`docs/`](docs/).

---

## Table of contents

1. [Big picture: two flows](#1-big-picture-two-flows)
2. [`training/train.py`](#2-trainingtrainpy)
3. [`app/main.py`](#3-appmainpy)
4. [Supporting modules (`model_loader`, `feature_client`, `metrics`)](#4-supporting-modules-model_loader-feature_client-metrics)
5. [How the important files connect](#5-how-the-important-files-connect)
6. [End-to-end checklist (train → Feast → serve)](#6-end-to-end-checklist-train--feast--serve)
7. [Conceptual questions (viva-style)](#7-conceptual-questions-viva-style)
8. [One-minute “best answer” script](#8-one-minute-best-answer-script)
9. [Appendix: demo commands & talking points](#appendix-demo-commands--talking-points)

---

## 1. Big picture: two flows

Your project has **two main flows**:

### A. Training flow

```
training/train.py
  → reads Kaggle fraudTrain.csv
  → cleans / prepares data
  → trains RandomForest pipeline (sklearn)
  → logs metrics + model to MLflow
  → registers model as Production
  → writes training/features.parquet
  → writes training/sample_request.json
```

### B. Serving / inference flow

```
app/main.py (+ model_loader, feature_client, metrics)
  → starts FastAPI
  → loads Production model from MLflow (once at startup)
  → initializes Feast FeatureStore client
  → receives POST /predict with entity_id
  → fetches online features from Feast → Redis
  → builds model input DataFrame (numerics from Feast + default categoricals)
  → runs predict / predict_proba
  → returns JSON + updates Prometheus metrics
```

**One sentence for the demo:** *`train.py` prepares the model **and** the offline feature table **feeding** Feast; `main.py` serves predictions using **MLflow’s Production model** plus **Feast’s online features**.*

---

## 2. `training/train.py`

### 2.1 Stated purpose (docstring)

The file trains a baseline fraud classifier, logs to MLflow, registers in the Model Registry (**Production**), and exports:

- `training/features.parquet`
- `training/sample_request.json`

So **three responsibilities:** (1) train, (2) register in MLflow, (3) export Feast-compatible feature data.

> **Demo tip:** Point to `feature_schema.py` and say *“this is the contract between training, Feast definitions, and inference.”*

### 2.2 Imports (what each group is for)

| Group | Role |
|-------|------|
| `json`, `os`, `pickle`, `sys`, `datetime`, `Path` | Env, paths, exit codes, timestamps, `sample_request.json`, local `model.pkl` |
| `numpy`, `pandas` | Arrays, CSV → DataFrame, Parquet export |
| **sklearn** `ColumnTransformer`, `Pipeline`, `RandomForestClassifier`, imputer, scaler, `OneHotEncoder`, metrics, `train_test_split` | Preprocessing + model + evaluation |
| `mlflow`, `mlflow.sklearn`, `MlflowClient` | Tracking, logging model artifact, **Production** transition |

### 2.3 Root path and `feature_schema`

`ROOT = Path(__file__).resolve().parent.parent` is the **project root**, so paths like `ROOT / "data/raw/fraudTrain.csv"` work no matter where you run the script from.

**Shared imports from `training/feature_schema.py`:**

| Symbol | Typical meaning |
|--------|------------------|
| `ENTITY_ID_COL` | `cc_num` — Feast entity / API `entity_id` |
| `TARGET_COL` | `is_fraud` |
| `RAW_TIMESTAMP_COL` | `trans_date_trans_time` (CSV) |
| `EVENT_TIMESTAMP_COL` | `event_timestamp` (Parquet / Feast) |
| `FEAST_NUMERIC_FEATURE_COLS` | Ordered numeric features aligned with Feast |

**Why it matters:** `train.py`, `feast_repo/feature_definitions.py`, and the API must agree on **names and semantics**.

### 2.4 Environment (`load_dotenv`)

Loads `.env` first, then `.env.example` for missing defaults (`override=False`). Typical variables: `MLFLOW_TRACKING_URI`, `MLFLOW_MODEL_NAME`, `FRAUD_TRAIN_PATH`, `TRAIN_MAX_ROWS`. Same code runs on laptop, VM, EC2, or CI.

> **Demo tip:** Contrast **host** `MLFLOW_TRACKING_URI=http://127.0.0.1:5000` with **inside the API container** `http://mlflow:5000` — same MLflow server, different DNS.

### 2.5 Constants

- **`RANDOM_STATE = 42`** — reproducible split and random pick for `sample_request.json`.
- **`MLFLOW_EXPERIMENT_NAME`** — default `modelserve_fraud`.
- **`MLFLOW_TRACKING_URI`** — where runs go.
- **`MODEL_PKL`, `PARQUET_OUT`, `SAMPLE_REQUEST`** — output paths.

### 2.6 `_nrows()` and `load_raw()`

- **`TRAIN_MAX_ROWS`** limits CSV rows (fast demos, CI).
- **`load_raw`** fails fast if CSV missing.

### 2.7 `main()` — training pipeline (high level)

1. Configure MLflow experiment.
2. Load and validate columns (`cc_num`, `is_fraud`, timestamp).
3. Build **`event_timestamp`**, **`gender_code`**, numeric **`zip`**, coerce transaction numerics.
4. Build **`y`**, filter invalid labels.
5. **`num_cols`** + **`cat_cols`** for the sklearn **Pipeline** (full raw columns).
6. **Feast export** uses only **`ENTITY_ID_COL`**, **`EVENT_TIMESTAMP_COL`**, **`FEAST_NUMERIC_FEATURE_COLS`** → **`features.parquet`**; cast **`cc_num`** to **int64** to match JSON integers in `/predict`.
7. **`train_test_split`** stratified 80/20.

> **Demo tip:** *“Training uses **both** numeric and categorical columns in the sklearn pipeline. Feast online features only carry the **numeric** slice; at predict time we fill **`unk`** for category/state/gender so the **same** pipeline runs.”*

### 2.8 Sklearn pipeline

- Numeric: median impute + scale.
- Categorical: `OneHotEncoder(handle_unknown="ignore", …)` so **`unk`** at inference is safe.
- **`RandomForestClassifier`** with **`class_weight="balanced"`** for fraud imbalance.
- The **serialized** object is the **full** `Pipeline` — MLflow serves that object from the registry.

### 2.9 MLflow: log model and move to Production

- **`mlflow.sklearn.log_model(..., registered_model_name=...)`** registers a **new version** from **memory** (not from reading `model.pkl` first).
- **`MlflowClient`** finds versions, picks latest, **`transition_model_version_stage(..., "Production", archive_existing_versions=True)`** so the API can resolve **`models:/modelserve_classifier/Production`**.

### 2.10 Artifacts on disk

| File | Purpose |
|------|---------|
| `training/model.pkl` | Local backup pickle; **API uses MLflow registry**, not this file by default |
| `training/features.parquet` | Feast offline path → materialize → **Redis** |
| `training/sample_request.json` | Valid **`entity_id`** picked from exported rows — ideal for live **`curl`** |

---

## 3. `app/main.py`

### 3.1 Role

FastAPI: **`/health`**, **`/metrics`**, **`POST /predict`**.

### 3.2 Alignment with training

- Same default **`MLFLOW_MODEL_NAME`** as training.
- **`_CAT_DEFAULTS`** (`category`, `state`, `gender` → **`unk`**) because Feast returns only numeric features; the **saved pipeline** still expects those columns.

### 3.3 Lifespan

1. **`model_loader.load_from_registry()`** — Production sklearn pipeline **once**.
2. **`metrics.set_served_model`** — Grafana/model version gauge.
3. **`FeastFeatureClient()`** — may patch Redis for Docker; failures can surface in **`/health`** as Feast degraded.

> **Demo tip:** *“Requirement: load model at **startup**, not per request.”*

### 3.4 `PredictRequest`

JSON **`{"entity_id": <int>}`** — **`cc_num`**.

### 3.5 `_build_model_frame`

Single-row DataFrame: numerics from Feast + defaults for categoricals, column order **`FEAST_NUMERIC_FEATURE_COLS` + categoricals**.

### 3.6 `/health` and `/metrics`

Health reflects model load and optional Feast init failure. Metrics expose Prometheus text for scraping.

### 3.7 `/predict`

Request counter → validate model & Feast → **`get_features(entity_id)`** → build frame → **`predict` / `predict_proba`** → latency histogram → JSON response.

**`fraud_probability`** = **`predict_proba[0][1]`** (probability of fraud class **1**).

> **Demo tip:** Flip one digit of **`entity_id`** → **`missing_features`** → proves you are not inventing feature vectors.

---

## 4. Supporting modules (`model_loader`, `feature_client`, `metrics`)

| Module | Responsibility |
|--------|------------------|
| **`app/model_loader.py`** | `mlflow.sklearn.load_model("models:/…/Production")`, **`predict(df)`**, version string, startup load errors surfaced to `/health` |
| **`app/feature_client.py`** | **`FeatureStore(repo_path=…)`**, **`get_online_features`** for **`fraud_txn_features:*`**, hit/miss metrics — **no raw Redis** in `main.py` |
| **`app/metrics.py`** | `prediction_requests_total`, `prediction_duration_seconds`, `prediction_errors_total`, Feast hit/miss, `model_version_info` |

---

## 5. How the important files connect

| Artifact / file | Produced by | Consumed by |
|-----------------|-------------|-------------|
| `training/feature_schema.py` | Maintained | `train.py`, Feast defs, API column order |
| `training/features.parquet` | `train.py` | `feast apply` + `materialize_features.py` → Redis |
| `training/sample_request.json` | `train.py` | Demo / CI **`curl`** |
| `feast_repo/feature_definitions.py` | Maintained | `feast -c feast_repo apply` |
| `feast_repo/feature_store.yaml` | Maintained | Redis connection + registry paths |
| `scripts/materialize_features.py` | Run after train + apply | Online store population |
| `docker-compose.yml` | Infra | Postgres, MLflow, Redis, API, Prometheus, Grafana |

---

## 6. End-to-end checklist (train → Feast → serve)

1. **`data/raw/fraudTrain.csv`**
2. **`docker compose up -d postgres redis mlflow`** (plus other services as needed)
3. **`python scripts/wait_for_mlflow.py`**
4. **`python training/train.py`** (optional **`TRAIN_MAX_ROWS`**)
5. MLflow UI: **Production** version
6. **`feast -c feast_repo apply`**
7. **`python scripts/materialize_features.py`**
8. **`docker compose up -d --build`**
9. **`curl`** `/health` and **`POST /predict`** with a materialized **`entity_id`**

**Per request:** lifespan-loaded model + Feast online read + pipeline inference + metrics.

---

## 7. Conceptual questions (viva-style)

| Question | Short answer |
|------------|----------------|
| Does training use Feast? | **No** — it **writes** `features.parquet`; Feast consumes it **after**. |
| Does inference use Feast? | **Yes** — online features for **`entity_id`**. |
| Why no Feast Docker container? | Feast is **library + CLI**; **Redis** is the online store process. |
| Registry vs `model.pkl`? | API loads from **MLflow Registry**; **`model.pkl`** is an optional local artifact. |

---

## 8. One-minute “best answer” script

**Training (`train.py`):**  
Reads **`fraudTrain.csv`**, builds numeric + categorical features, fits a **sklearn Pipeline**, logs metrics and the **full pipeline** to MLflow, registers **`modelserve_classifier`**, promotes latest version to **Production**, writes **`features.parquet`** for Feast and **`sample_request.json`** for testing.

**Serving (`main.py`):**  
On startup, loads **Production** from MLflow **once** and initializes **Feast**. On **`POST /predict`**, accepts **`entity_id`** (**`cc_num`**), **fetches online features** via the Feast SDK from **Redis**, adds **default categoricals**, runs **predict / predict_proba**, returns **prediction**, **fraud_probability**, **model_version**, and exposes **Prometheus** metrics — satisfying the original incomplete line in the `.txt`: *uses Feast SDK to fetch online features for that entity, assemble the sklearn input row, run the loaded pipeline, and return JSON.*

---

## Appendix: demo commands & talking points

```bash
curl -s http://localhost:8000/health | python -m json.tool

curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d "{\"entity_id\": YOUR_ENTITY_ID}"

curl -s http://localhost:8000/metrics | head -40
```

**Talking points:**

1. **Train/serve skew:** Same **`feature_schema`** numerics as Feast; categoricals filled consistently with training **`fillna("unk")`** + encoder **`handle_unknown="ignore"`**.
2. **Why timestamp in Parquet:** Feast uses **`event_timestamp`** for point-in-time correctness and materialization windows.
3. **Monitoring:** Request rate, latency histogram, errors, Feast ratio — tie **technical** metrics to **business** risk discussion (fraud).

---

*Canonical Markdown narrative for demos; the raw scratch file `explanation-linewise.txt` remains available alongside this file.*
