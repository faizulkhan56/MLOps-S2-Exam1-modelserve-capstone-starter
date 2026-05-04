# ModelServe-new

> **MLOps with Cloud — Season 2, Capstone (Poridhi.io)**

Production-style ML serving: **FastAPI** inference, **MLflow** registry, **Feast** + **Redis** online features, **Postgres**, **Prometheus**, **Grafana**, **Docker Compose** locally and on **AWS EC2**, with **Pulumi** infrastructure and **GitHub Actions** CI/CD.

| Phase | Delivered in this repo |
|-------|-------------------------|
| **1–2** | Compose stack, API skeleton, monitoring bootstrap |
| **3–4** | Training, MLflow Production model, Feast apply + Redis materialize |
| **5–6** | Registry-backed inference, `/predict`, tests |
| **7–8** | Prometheus/Grafana dashboards & alerts; hardened API Dockerfile |
| **9–10** | Pulumi (VPC, EC2, EIP, S3, ECR); EC2 deploy scripts |
| **11–12** | GitHub Actions deploy/destroy; pipeline Kaggle + `deploy_ec2.sh` |
| **13–14** | Runbooks, troubleshooting, architecture summary, **submission** & **viva** docs |

---

## Prerequisites

- **Docker** and **Docker Compose** v2
- **Python 3.10+** for host-side training/scripts (optional for “Docker only” workflows)

## Quick start (local stack)

1. **Env file (optional)** — defaults work; override ports/credentials in `.env`:

   ```bash
   cp .env.example .env
   ```

2. **Start the stack**

   ```bash
   docker compose up -d --build
   ```

3. **Check services**

   ```bash
   docker compose ps
   ```

4. **Smoke tests**

   | Check | Command | Expected |
   |--------|---------|----------|
   | API health | `curl -s http://localhost:8000/health` | JSON: `status` (after training + full stack: `healthy` with `model_version`) |
   | API metrics | `curl -s http://localhost:8000/metrics` | Prometheus text (e.g. `prediction_requests_total`, `prediction_duration_seconds_*`) |
   | MLflow | Open `http://localhost:5000` | UI loads |
   | Redis | `docker compose exec redis redis-cli PING` | `PONG` |
   | Prometheus | `http://localhost:9090/targets` | `modelserve-api`, `node-exporter` **UP** |
   | Grafana | `http://localhost:3001` | UI (default host port; see `GRAFANA_PORT` in `.env`) |

5. **Base services only** (train / Feast path)

   ```bash
   docker compose up -d postgres redis mlflow
   ```

6. **Stop**

   ```bash
   docker compose down
   ```

### Grafana: `failed to bind host port 0.0.0.0:3000`

Compose publishes **`${GRAFANA_PORT:-3001}`**. If the error shows **3000**, your **`.env`** likely sets `GRAFANA_PORT=3000`. Use **`3001`** or remove the line, then `docker compose down` and `docker compose up -d`. Optional: set **`GF_SERVER_ROOT_URL`** in `.env` to match the host port you use (see `docker-compose.yml`).

### MLflow: `PermissionError` … `'/mlflow'` when running `training/train.py` on the host

The server must **serve** artifacts so the client does not try to write local `file:` paths. This repo’s **MLflow** service uses `--serve-artifacts` and `--artifacts-destination` (see `docker-compose.yml`). Restart MLflow and re-run training.

### MLflow: `No module named 'psycopg2'`

Use the custom image:

```bash
docker compose build --no-cache mlflow
docker compose up -d
```

---

## API endpoints (inference)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness; model version when loaded |
| `GET` | `/metrics` | Prometheus metrics |
| `POST` | `/predict` | JSON body `{"entity_id": <int>}` — Feast entity `cc_num` |

Example:

```bash
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d "{\"entity_id\": 1234567890123456}"
```

Use a valid **`entity_id`** after train + materialize (see `training/sample_request.json`).

---

## Environment variables

See **[`.env.example`](.env.example)** for ports, MLflow/Feast, Grafana, and API defaults.

---

## CI/CD & GitHub Secrets

Push to **`main`** runs **Deploy (Pulumi + EC2)**; **Destroy** is manual (`workflow_dispatch`).

**Secrets list, SSH keys, Kaggle, Pulumi token:** **[`docs/github-secrets.md`](docs/github-secrets.md)**

---

## Dataset (Kaggle — training)

**https://www.kaggle.com/datasets/kartik2112/fraud-detection**

| Item | Notes |
|------|--------|
| Training file | `fraudTrain.csv` → e.g. `data/raw/` (large; **gitignored**) |
| Entity | **`cc_num`** → Feast entity and **`entity_id`** in `/predict` |

---

## Phases 3–4 — minimal train + Feast (host)

**Prereqs:** Compose up with **postgres**, **redis**, **mlflow**; `data/raw/fraudTrain.csv`; **`MLFLOW_TRACKING_URI=http://127.0.0.1:5000`** in `.venv` env.

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
docker compose up -d postgres redis mlflow
python scripts/wait_for_mlflow.py
# optional: export TRAIN_MAX_ROWS=50000
python training/train.py
feast -c feast_repo apply
python scripts/materialize_features.py
docker compose up -d --build
```

Registry model: **`modelserve_classifier`** → **Production**.  
Feast: apply from repo root: **`feast -c feast_repo apply`**.

---

## After `git pull` (VM / new machine)

Large artifacts and secrets are not in git. Recreate **`.env`**, **Kaggle data**, re-run **train** + **Feast** as needed. See **[`docs/final-runbook.md`](docs/final-runbook.md)** and **[`docs/troubleshooting.md`](docs/troubleshooting.md)**.

```bash
git pull
cp -n .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d --build
python scripts/wait_for_mlflow.py
python training/train.py
feast -c feast_repo apply
python scripts/materialize_features.py
```

---

## Documentation (Phase 13–14)

| Document | Purpose |
|----------|---------|
| [`docs/architecture-summary.md`](docs/architecture-summary.md) | One-page architecture & flows |
| [`docs/final-runbook.md`](docs/final-runbook.md) | Local + EC2 + CI operations, cleanup |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | Common errors and fixes |
| [`docs/demo-guide.md`](docs/demo-guide.md) | Live demo checklist |
| [`docs/github-secrets.md`](docs/github-secrets.md) | Actions secrets & SSH key setup |
| [`docs/submission-checklist.md`](docs/submission-checklist.md) | **Submission:** screenshots, demo script, curl shapes, limitations |
| [`docs/viva-questions.md`](docs/viva-questions.md) | **Oral exam** Q&A |
| [`explanation-linewise.md`](explanation-linewise.md) | **Train + Feast + MLflow + API** narrative (demo / viva), expands `explanation-linewise.txt` |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Full engineering template (rubric) |

---

## License / course

*MLOps with Cloud — Season 2, Capstone: ModelServe | Poridhi.io*
