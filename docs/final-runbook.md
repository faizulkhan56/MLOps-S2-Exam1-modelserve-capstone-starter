# ModelServe — Final runbook (Phase 13)

Operational procedures for **local**, **EC2**, and **CI/CD**. Deep secret setup: [`github-secrets.md`](github-secrets.md).

---

## 1. Architecture flow (one paragraph)

Code changes land in **Git** → **push to `main`** triggers **GitHub Actions** (`deploy.yml`): **Pulumi** provisions or updates **VPC + subnet + SG + EC2 + EIP + S3 + ECR** in `ap-southeast-1`, then the runner **SSHs** to the instance, runs **`deploy_ec2_pipeline.sh`** (Kaggle download + `deploy_ec2.sh`), which brings up **Docker Compose**, **trains** (optional row cap), **Feast apply + materialize**, starts **API + monitoring**, and checks **`/health`**. Locally, the same Compose stack runs without Pulumi.

---

## 2. Local setup (from a fresh clone)

```bash
cd MLOps-S2-Exam1-modelserve-capstone-starter
cp .env.example .env
docker compose up -d --build
```

**Optional — full ML path on the host** (Python venv):

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/wait_for_mlflow.py
# Place Kaggle data: data/raw/fraudTrain.csv (see README / Kaggle)
python training/train.py
feast -c feast_repo apply
python scripts/materialize_features.py
docker compose up -d --build
curl -s http://localhost:8000/health
```

**Smoke checks**

| Check | Command |
|--------|---------|
| API | `curl -s http://localhost:8000/health` |
| Predict | `curl -s -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d "{\"entity_id\": <int>}"` |
| MLflow | Browser: `http://localhost:5000` |
| Prometheus | `http://localhost:9090/targets` |
| Grafana | `http://localhost:3001` (default; see `.env` / `GF_SERVER_ROOT_URL`) |
| Redis | `docker compose exec redis redis-cli PING` |

**Stop local stack**

```bash
docker compose down
```

---

## 3. EC2 deployment (manual operator)

Prerequisites: **Pulumi stack** applied at least once; you can **SSH** as `ubuntu` to the **Elastic IP**; Docker from user-data is running.

**Clone + env + stack (typical)**

```bash
export MODELSERVE_REPO_URL="https://github.com/<ORG>/<REPO>.git"
export MODELSERVE_BRANCH="main"
# Optional: MODELSERVE_HOME defaults to ~/modelserve
./scripts/deploy_ec2.sh
```

**CI-style full path** (Kaggle + dataset + same deploy script):

```bash
export MODELSERVE_REPO_URL="https://github.com/<ORG>/<REPO>.git"
export KAGGLE_USERNAME="..."
export KAGGLE_KEY="..."
./scripts/deploy_ec2_pipeline.sh
```

**After deploy — public URLs** (replace `<EIP>` with `pulumi stack output instance_public_ip` or AWS console)

- API health: `http://<EIP>:8000/health`
- MLflow: `http://<EIP>:5000`
- Grafana: `http://<EIP>:3001`
- Prometheus: `http://<EIP>:9090`

---

## 4. GitHub secrets (summary)

| Secret | Purpose |
|--------|---------|
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` | Pulumi AWS provider |
| `PULUMI_ACCESS_TOKEN` | Non-interactive `pulumi login` |
| `SSH_PUBLIC_KEY` | Pulumi `sshPublicKey` → EC2 `authorized_keys` |
| `SSH_PRIVATE_KEY` | Actions `scp`/`ssh` to `ubuntu@<EIP>` |
| `KAGGLE_USERNAME` / `KAGGLE_KEY` | Pipeline Kaggle download on EC2 |
| `PULUMI_CONFIG_PASSPHRASE` | Optional; encrypted stack config |

Full table and key generation: [`github-secrets.md`](github-secrets.md).

**Private GitHub repo:** default clone URL has **no token**; use a public repo or add PAT/deploy-key flow yourself.

---

## 5. CI/CD flow

| Workflow | Trigger | What it does |
|----------|---------|----------------|
| `.github/workflows/deploy.yml` | **Push to `main`** | Checkout → AWS creds → Pulumi CLI → `infrastructure/` venv → select/init stack **`dev`** → `pulumi config` (`aws:region`, `sshPublicKey`) → **`pulumi up --yes`** → wait for **`sudo docker info`** on EC2 → `scp` **`scripts/deploy_ec2_pipeline.sh`** → run with env (`MODELSERVE_REPO_URL`, branch, Kaggle secrets). |
| `.github/workflows/destroy.yml` | **workflow_dispatch** (manual) | Same bootstrap → **`pulumi destroy --yes`** on stack **`dev`**. On failure, logs suggested **`pulumi state delete 'urn:...'`** lines (manual only). |

**Concurrency:** deploy workflow uses a concurrency group so overlapping pushes to `main` do not stomp each other.

---

## 6. `entity_id` (predict API)

- **`entity_id`** in `POST /predict` is the **Feast entity join key**: **`cc_num`** (credit card number from the Kaggle schema), as **integer**.
- The API loads **online features** for that `cc_num` from the **`fraud_txn_features`** view; if the entity was **never materialized**, the request fails with a structured error (missing features).
- Use a value that exists in **`training/features.parquet`** / materialized Redis (see `training/sample_request.json` after a successful train, or pick from training export).

---

## 7. Feast / MLflow recap

- **MLflow**: source of truth for **which model** runs in Production (`modelserve_classifier`). The API loads once at startup.
- **Feast**: source of truth for **which feature vector** is used for that `cc_num` at inference time, via the **SDK** and **Redis** online store (after `materialize_features.py`).

---

## 8. Cleanup / destroy

### Local

```bash
docker compose down
# Optional volumes wipe (destructive):
# docker compose down -v
```

### AWS + Pulumi

1. GitHub: **Actions** → **Destroy (Pulumi)** → **Run workflow**.
2. If destroy fails, follow the **printed URNs** with `pulumi state delete '...'` locally, then rerun the workflow.
3. Or from laptop (with AWS + Pulumi configured):

```bash
cd infrastructure
source venv/bin/activate   # or create venv + pip install -r requirements.txt
pulumi login
pulumi stack select dev
pulumi destroy --yes
```

**S3 / ECR**: bucket and repos are defined with destroy-friendly options in Pulumi; verify empty ECR repos before destroy if your org enforces policies.

---

## 9. Quick reference — important paths

| Path | Role |
|------|------|
| `docker-compose.yml` | Stack definition |
| `.env.example` | Documented defaults |
| `training/train.py` | Train + register + Parquet export |
| `scripts/materialize_features.py` | Redis materialize |
| `feast_repo/` | Feast definitions |
| `monitoring/prometheus/` | Scrape + alert rules |
| `monitoring/grafana/` | Provisioning + dashboard JSON |
| `infrastructure/__main__.py` | AWS infra |
| `.github/workflows/deploy.yml` | CI deploy |
