# ModelServe — Troubleshooting (Phase 13)

Common errors and **practical fixes**. For secret setup and CI checklist, see [`github-secrets.md`](github-secrets.md). For operations, see [`final-runbook.md`](final-runbook.md).

---

## 1. API / FastAPI

### `/health` shows `degraded` or `model_version: not_loaded`

- **Cause:** MLflow unreachable or no Production model, or load exception at startup.
- **Fix:** `docker compose ps` → ensure **mlflow** healthy. On host: `curl -s http://127.0.0.1:5000`. Run **`python scripts/wait_for_mlflow.py`** then **`python training/train.py`**. Check API logs: `docker compose logs api --tail=100`.

### `POST /predict` → missing features / 404-style error body

- **Cause:** `entity_id` (`cc_num`) not in Feast online store (not materialized or wrong id).
- **Fix:** Confirm **`training/features.parquet`** exists; run **`feast -c feast_repo apply`** and **`python scripts/materialize_features.py`**. Use an entity from the training export or `training/sample_request.json`.

### `503` feast_unavailable

- **Cause:** `FeatureStore` init failed (e.g. missing `feast_repo` registry in image, or Redis connection from container).
- **Fix:** Rebuild API after Feast/registry changes: **`docker compose build api && docker compose up -d api`**. Verify Redis: **`docker compose exec redis redis-cli PING`**.

---

## 2. MLflow

### `No module named 'psycopg2'` (MLflow container)

- **Fix:** Use repo’s **custom MLflow image**: **`docker compose build --no-cache mlflow`** then **`docker compose up -d mlflow`**.

### `PermissionError` … `/mlflow` when training **on the host**

- **Cause:** Client tried to write host path for artifacts.
- **Fix:** MLflow server must run with **`--serve-artifacts`** and **`--artifacts-destination`** (already in compose). Restart MLflow and re-run training.

---

## 3. Feast

### `feast apply` cannot find `feature_store.yaml`

- **Fix:** Run from repo root: **`feast -c feast_repo apply`** (not bare `feast apply`).

### Redis / connection string errors (`invalid literal for int()`)

- **Cause:** Wrong `connection_string` format in `feast_repo/feature_store.yaml` for this Feast + redis-py combo.
- **Fix:** Use **`host:port,db=0`** form (see comments in that file). Host-side materialize uses **`127.0.0.1`**; API container uses patched Redis host via app code when `REDIS_URL` is set (see `app/feature_client.py`).

### Materialize shows errors or 0 rows

- **Cause:** Missing or empty **`training/features.parquet`**.
- **Fix:** Run **`training/train.py`** first.

---

## 4. Grafana / ports

### `bind ... 3000` already allocated

- **Cause:** `.env` sets **`GRAFANA_PORT=3000`** or another process uses 3000.
- **Fix:** Set **`GRAFANA_PORT=3001`** (or free the port), **`docker compose down`** and **`up`**. Align **`GF_SERVER_ROOT_URL`** in `.env` if you override host port (see `.env.example` / compose comments).

---

## 5. Prometheus

### Alert rules show empty in `/api/v1/rules`

- **Cause:** Invalid PromQL or YAML in `monitoring/prometheus/alerts.yml`, or `rule_files` path wrong.
- **Fix:** Use **single-line `expr:`** in alerts; ensure **`rule_files`** in `prometheus.yml` resolves (e.g. `alerts.yml` next to config in container). **`docker compose restart prometheus`**.

### Targets down

- **Fix:** Ensure **api**, **node-exporter**, and Prometheus itself are on the same Compose network; check firewall/SG on EC2 (ports **8000**, **9100**, **9090**).

---

## 6. Docker / Compose

### API image stale after `git pull`

- **Fix:** **`docker compose build api && docker compose up -d api`** (API has no bind mount for `app/` in default compose).

### Only postgres + mlflow + redis running

- **Cause:** Partial **`docker compose up`**.
- **Fix:** **`docker compose up -d`** for full stack when you need API + monitoring.

---

## 7. Pulumi / AWS

### `EntityAlreadyExists` (IAM role, etc.)

- **Cause:** Name collision with orphaned AWS objects vs Pulumi state.
- **Fix:** This repo’s current infra may omit IAM instance profile; if you still see IAM errors, align **code** with **state** (import or delete orphans in AWS) per instructor runbook.

### Wrong region

- **Fix:** **`pulumi config set aws:region ap-southeast-1`** and GitHub **`AWS_REGION`** secret must match.

---

## 8. GitHub Actions / CI

### Pulumi login fails

- **Fix:** Set **`PULUMI_ACCESS_TOKEN`** (and optional **`PULUMI_CONFIG_PASSPHRASE`**).

### SSH / `scp` fails after Pulumi

- **Fix:** **`SSH_PUBLIC_KEY`** must match **`SSH_PRIVATE_KEY`** pair; same key as Pulumi **`sshPublicKey`**. Wait step ensures Docker is up before SSH.

### `git clone` fails on EC2

- **Cause:** **Private** repo without credentials.
- **Fix:** Use a **public** repo for the default pipeline, or add PAT/deploy key (custom change outside this doc).

### Kaggle download fails in pipeline

- **Fix:** Valid **`KAGGLE_USERNAME`** / **`KAGGLE_KEY`** secrets; account accepted dataset rules on Kaggle.

---

## 9. Cleanup mistakes

### Destroy stuck on IAM (legacy stacks)

- **Fix:** GitHub **Destroy** workflow prints **`pulumi state delete 'urn:...'`** hints — run locally, then **rerun destroy**. Do not delete state blindly without understanding impact.

---

## 10. Getting more help

1. Reproduce with **minimal commands** from [`final-runbook.md`](final-runbook.md).
2. Collect **logs**: `docker compose logs <service> --tail=200`.
3. For CI: export the **failed job log** from GitHub Actions.
