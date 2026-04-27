#!/usr/bin/env bash
# Phase 10 — EC2 runtime deployment order for ModelServe (single host + docker compose).
#
# Prerequisites on EC2:
#   - Pulumi user-data completed (Docker, Compose plugin, AWS CLI, Git, unzip)
#   - SSH as ubuntu; clone URL reachable from instance
#
# Usage:
#   export MODELSERVE_REPO_URL="https://github.com/ORG/MLOps-S2-Exam1-modelserve-capstone-starter.git"
#   export MODELSERVE_BRANCH="main"   # optional
#   export MODELSERVE_HOME="$HOME/modelserve"   # optional
#   ./scripts/deploy_ec2.sh
#
# Order (must match capstone):
#   1. clone/pull repo
#   2. .env from .env.example
#   3. production-oriented env vars (public URLs from instance metadata)
#   4. venv + pip install
#   5. postgres + redis + mlflow
#   6. wait for MLflow
#   7. train (if Kaggle CSV present) OR skip with message
#   8. feast apply
#   9. materialize_features
#  10. full compose stack + /health check

set -euo pipefail

REPO="${MODELSERVE_REPO_URL:?Set MODELSERVE_REPO_URL to your git HTTPS/SSH URL}"
BRANCH="${MODELSERVE_BRANCH:-main}"
ROOT="${MODELSERVE_HOME:-$HOME/modelserve}"

ec2_public_ip() {
  local token
  token="$(curl -sS -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")"
  curl -sS -H "X-aws-ec2-metadata-token: ${token}" \
    "http://169.254.169.254/latest/meta-data/public-ipv4"
}

echo "==> [1] Clone or pull repository"
if [[ -d "${ROOT}/.git" ]]; then
  git -C "${ROOT}" fetch --all --prune
  git -C "${ROOT}" checkout "${BRANCH}"
  git -C "${ROOT}" pull --ff-only
else
  mkdir -p "$(dirname "${ROOT}")"
  git clone -b "${BRANCH}" "${REPO}" "${ROOT}"
fi
cd "${ROOT}"

PUB_IP="$(ec2_public_ip)"
echo "Detected public IPv4: ${PUB_IP}"

echo "==> [2] Create .env from template"
if [[ ! -f .env ]]; then
  cp .env.example .env
fi

echo "==> [3] Set production-oriented URLs (append if missing)"
touch .env
grep -q '^MLFLOW_PUBLIC_URI=' .env && sed -i "s|^MLFLOW_PUBLIC_URI=.*|MLFLOW_PUBLIC_URI=http://${PUB_IP}:5000|" .env || echo "MLFLOW_PUBLIC_URI=http://${PUB_IP}:5000" >> .env
# Compose reads host port mapping; Grafana root URL for links in emails/UI:
grep -q '^GF_SERVER_ROOT_URL=' .env && sed -i "s|^GF_SERVER_ROOT_URL=.*|GF_SERVER_ROOT_URL=http://${PUB_IP}:3001|" .env || echo "GF_SERVER_ROOT_URL=http://${PUB_IP}:3001" >> .env

echo "==> [4] Python venv and dependencies"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "==> [5] Start postgres, redis, mlflow"
docker compose up -d postgres redis mlflow

echo "==> [6] Wait for MLflow readiness"
python scripts/wait_for_mlflow.py

echo "==> [7] Train + register (requires data/raw/fraudTrain.csv) or skip"
if [[ -f data/raw/fraudTrain.csv ]]; then
  python training/train.py
else
  echo "WARN: data/raw/fraudTrain.csv not found — upload Kaggle data then run: python training/train.py" >&2
fi

if [[ ! -f training/features.parquet ]]; then
  echo "ERROR: training/features.parquet missing (run training/train.py after placing data/raw/fraudTrain.csv)." >&2
  exit 1
fi

echo "==> [8] Feast apply"
feast -c feast_repo apply

echo "==> [9] Materialize online features"
python scripts/materialize_features.py

echo "==> [10] Start full stack (api, prometheus, grafana, node-exporter, …)"
docker compose up -d --build

sleep 5
echo "==> Validate /health"
curl -fsS "http://127.0.0.1:8000/health" | python -m json.tool
echo "OK: deploy_ec2.sh finished. Public endpoints (use Elastic IP / Pulumi output):"
echo "  API:         http://${PUB_IP}:8000/health"
echo "  MLflow:      http://${PUB_IP}:5000"
echo "  Prometheus: http://${PUB_IP}:9090"
echo "  Grafana:     http://${PUB_IP}:3001"
