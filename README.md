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
   | Grafana | `http://localhost:3000` (default `admin` / `admin` unless set in `.env`) | UI loads; Prometheus datasource and placeholder dashboard provisioned |

5. **Base services only (optional sequence from the operations playbook)**
   ```bash
   docker compose up -d postgres redis mlflow
   ```
   Then verify Postgres is healthy, Redis PING, MLflow UI on port **5000**.

6. **Stop**
   ```bash
   docker compose down
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

## Dataset (training)

Fraud dataset (Kaggle): [Credit Card Transactions Fraud Detection](https://www.kaggle.com/datasets/kartik2112/fraud-detection) — use `fraudTrain.csv`; entity id **`cc_num`**.

---

*MLOps with Cloud — Season 2, Capstone: ModelServe | Poridhi.io*
