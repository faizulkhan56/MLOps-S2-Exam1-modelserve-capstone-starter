# ModelServe

> MLOps with Cloud — Season 2, Capstone (ModelServe)

A production-style ML serving stack: FastAPI, MLflow, Feast, Redis, Postgres, Prometheus, and Grafana, with Pulumi and GitHub Actions in later phases.

**Phases 1–2 (current):** repository bootstrap and a **local Docker Compose** stack. Inference, MLflow registration, and Feast are implemented in **Phases 3–4+**.

## Prerequisites

- **Docker** and **Docker Compose** v2
- (Optional) **Python 3.10+** for local scripts **outside** containers

## Quick start (local stack)

1. **Optional** — use a local env file for ports and secrets (defaults work for Compose):
   ```bash
   cp .env.example .env
   # edit as needed; Compose also reads `.env` for variable substitution when present
   ```

2. **Build and start all services** (or start base services first, see below):
   ```bash
   docker compose up -d --build
   ```

3. **Check containers:**
   ```bash
   docker compose ps
   ```

4. **Smoke tests**

   | Check | Command | Expected |
   |-------|---------|----------|
   | API health | `curl -s http://localhost:8000/health` | JSON with `"status": "healthy"`, `"model_version": "not_loaded"` |
   | API metrics | `curl -s http://localhost:8000/metrics` | Prometheus text; includes `modelserve_` and default process metrics |
   | MLflow UI | open `http://localhost:5000` | MLflow home page |
   | Redis | `docker compose exec redis redis-cli PING` | `PONG` |
   | Prometheus | `http://localhost:9090/targets` | `modelserve-api` and `node-exporter` **UP** |
   | Grafana | `http://localhost:3001` (default host port; override `GRAFANA_PORT` in `.env`) | UI loads; Prometheus datasource and placeholder dashboard provisioned |

5. **Base services only (optional sequence from the operations playbook)**
   ```bash
   docker compose up -d postgres redis mlflow
   ```
   Then verify Postgres is healthy, Redis PING, MLflow UI on port **5000**.

6. **Stop**
   ```bash
   docker compose down
   ```

### Grafana: `failed to bind host port 0.0.0.0:3000`

Compose publishes **`${GRAFANA_PORT:-3001}`** on the host. If the error still mentions **port 3000**, a **`.env`** file in the project root almost certainly has **`GRAFANA_PORT=3000`** (often copied from an old template). That value **overrides** the 3001 default. Edit `.env` to `GRAFANA_PORT=3001` or **remove** the line, then `docker compose down` and `docker compose up -d`. Confirm with `docker compose config | grep -A2 grafana` (published port should be **3001**).

### MLflow + Postgres: `No module named 'psycopg2'`

The stock `ghcr.io/mlflow/mlflow` image does not ship the PostgreSQL driver. This repo builds **`modelserve-mlflow:local`** from `docker/mlflow/Dockerfile`, which extends that image and installs `psycopg2-binary` (and `boto3` for S3 later). If you still see the error after pulling changes:

```bash
docker compose build --no-cache mlflow
docker compose up -d
```

## REST endpoints (Phases 1–2)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness; model not yet loaded from registry |
| GET | `/metrics` | Prometheus metrics |

`POST /predict` and `GET /predict/{id}?explain=true` are added in **Phase 5**.

## Environment variables

See **`.env.example`** for port defaults, future MLflow/Feast settings, and Grafana admin credentials.

## GitHub Secrets

(Added when CI/CD is implemented.) See `.env.example` and future `docs/ARCHITECTURE.md`.

## Engineering documentation

Full design, ADRs, and runbook: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (to be completed per exam rubric).

## Dataset (Kaggle — required for training)

Official dataset page (download via Kaggle UI or API after `kaggle datasets download`):

**https://www.kaggle.com/datasets/kartik2112/fraud-detection**

| Item | Notes |
|------|--------|
| Primary file | `fraudTrain.csv` (~1.3M rows) for training; `fraudTest.csv` optional for holdout |
| Entity key | **`cc_num`** (credit card number) — used as Feast entity and API `entity_id` |
| Local path | Keep CSVs **outside git** (large); point `training/train.py` at your path, e.g. `data/raw/` (add `data/` to `.gitignore` if you create it) |

---

## Phase 3 & Phase 4 — plan (before implementation)

Use this checklist after Phases 1–2 are green. **Do not start Pulumi / CI** until this local path works.

### Phase 3 — MLflow registration

1. Implement or finish **`training/train.py`**: load `fraudTrain.csv`, train a sklearn-compatible model, log metrics/params, save **`training/`** or **`provided/`** model artifact (`.pkl` under the exam’s size limit), register to MLflow **or** emit `.pkl` for a separate register step.
2. Add **`scripts/wait_for_mlflow.py`**: block until `MLFLOW_TRACKING_URI` (e.g. `http://localhost:5000`) is ready.
3. Add **`scripts/register_model.py`**: load `.pkl`, `mlflow.register_model` (or `log` + `register`), set **Production** stage (or your chosen alias), print version id.
4. **Validate:** MLflow UI shows model + version in **Production**; optional `mlflow.pyfunc.load_model` smoke test from host.
5. Update **`requirements.txt`** with `mlflow`, `scikit-learn`, `pandas`, `numpy` (and pins as needed); rebuild **api** image when you add deps for containers.

### Phase 4 — Feast (Redis online store)

1. Complete **`feast_repo/feature_store.yaml`**: `registry` path, **Redis** online store (host `redis` in Compose), **parquet** offline source pointing at **`training/features.parquet`** (produced in training).
2. Complete **`feast_repo/feature_definitions.py`**: entity **`cc_num`**, feature view(s) aligned with Parquet columns.
3. Run **`feast apply`** (from `feast_repo/` with Redis up).
4. Implement **`scripts/materialize_features.py`**: `materialize` / `materialize-incremental` for a window covering your data; print sample entity id for tests.
5. **Validate:** `feast` CLI lists entities/views; **Python** `get_online_features` for one `cc_num` returns rows.

**Then:** Phase 5 wires FastAPI to MLflow registry + Feast SDK (`POST /predict`, explain route, full metrics).

---

*MLOps with Cloud — Season 2, Capstone: ModelServe | Poridhi.io*
