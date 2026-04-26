# ModelServe

> MLOps with Cloud — Season 2, Capstone (ModelServe)

A production-style ML serving stack: FastAPI, MLflow, Feast, Redis, Postgres, Prometheus, and Grafana, with Pulumi and GitHub Actions in later phases.

**Phases 1–2:** Docker Compose stack. **Phases 3–4:** training, MLflow registry, Feast + Redis (implemented in this repo — see below).

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

## Phase 3 & Phase 4 — runbook (on laptop or Poridhi VM)

**Prereqs:** Phases 1–2 green; Kaggle `fraudTrain.csv` at `data/raw/fraudTrain.csv` (or set `FRAUD_TRAIN_PATH`).

1. **Python env** (same machine you run `docker compose` and scripts):
   ```bash
   python3.10 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -U pip
   pip install -r requirements.txt
   ```

2. **Env file for host scripts** — `cp .env.example .env` and keep **`MLFLOW_TRACKING_URI=http://127.0.0.1:5000`** (training talks to the published MLflow port, not the `mlflow` Docker hostname).

3. **Start backing services** (at least MLflow + Postgres; Redis for Phase 4):
   ```bash
   docker compose up -d postgres redis mlflow
   python scripts/wait_for_mlflow.py
   ```

4. **Phase 3 — train + register (optional: limit rows for a quick test)**
   ```bash
   # export TRAIN_MAX_ROWS=50000   # optional dev shortcut
   python training/train.py
   ```
   Produces: `training/model.pkl`, `training/features.parquet`, `training/sample_request.json`, and registers **`modelserve_classifier`** → **Production** in MLflow.

5. **Phase 4 — Feast**
   ```bash
   feast -c feast_repo apply
   python scripts/materialize_features.py
   ```
   `feature_store.yaml` uses **`redis://127.0.0.1:6379/0`** for materialization from the **host** (same as Compose-published Redis). If you **materialize from inside a container** later, use `redis://redis:6379/0` in a copy of the config or override via doc.

6. **Validate**
   - MLflow UI: model version in **Production**.
   - `head training/sample_request.json` — use `entity_id` in later API tests.

**Then:** Phase 5 = FastAPI loads this model from the registry and reads features via Feast (`POST /predict`, explain, metrics).

---

## After `git push` — what to do on the Poridhi VM

Git **does not** contain large or secret files. Expect to recreate these **on the VM** after `git pull`:

| Not in git (typical) | What to do on Poridhi |
|----------------------|------------------------|
| `data/**` (Kaggle CSV) | Download the dataset again (or `scp` from laptop), e.g. `data/raw/fraudTrain.csv` |
| `.env` | `cp .env.example .env` and edit (ports, `MLFLOW_TRACKING_URI`, Grafana password, etc.) |
| `training/model.pkl`, `training/features.parquet` | Re-run `python training/train.py` (or copy from laptop if you must — usually **re-train** on VM) |
| `feast_repo/data/registry.db` | Re-run `feast -c feast_repo apply` |
| Redis / MLflow / Postgres **data** in Docker volumes | `docker compose up` uses existing **named volumes** on that machine; first time: empty DBs, so re-run **train** + **materialize** anyway |

**Minimal VM sequence after pull:**

```bash
git pull
cd /path/to/MLOps-S2-Exam1-modelserve-capstone-starter
cp -n .env.example .env   # or create .env; set MLFLOW_TRACKING_URI etc.
python3.10 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# place Kaggle CSV under data/raw/ or set FRAUD_TRAIN_PATH
docker compose up -d --build
python scripts/wait_for_mlflow.py
python training/train.py
feast -c feast_repo apply
python scripts/materialize_features.py
```

**Grafana** defaults to host port **3001** if you use the repo’s `docker-compose.yml` defaults — adjust `.env` if the lab still conflicts.

---

*MLOps with Cloud — Season 2, Capstone: ModelServe | Poridhi.io*
