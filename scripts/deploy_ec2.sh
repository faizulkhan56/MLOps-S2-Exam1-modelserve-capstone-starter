#!/usr/bin/env bash
# Phase 10 — EC2 runtime deployment order for ModelServe (single host + docker compose)

set -euo pipefail

REPO="${MODELSERVE_REPO_URL:-https://github.com/faizulkhan56/MLOps-S2-Exam1-modelserve-capstone-starter.git}"
BRANCH="${MODELSERVE_BRANCH:-main}"
ROOT="${MODELSERVE_HOME:-$HOME/modelserve}"

ec2_public_ip() {
  local token
  token="$(curl -sS -X PUT http://169.254.169.254/latest/api/token \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")"

  curl -sS \
    -H "X-aws-ec2-metadata-token: ${token}" \
    http://169.254.169.254/latest/meta-data/public-ipv4
}

echo "==> [1] Clone / Pull repository"

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
echo "Detected Public IP: ${PUB_IP}"

echo "==> [2] Create .env"

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

echo "==> [3] Inject production URLs"

touch .env

grep -q '^MLFLOW_PUBLIC_URI=' .env \
  && sed -i "s|^MLFLOW_PUBLIC_URI=.*|MLFLOW_PUBLIC_URI=http://${PUB_IP}:5000|" .env \
  || echo "MLFLOW_PUBLIC_URI=http://${PUB_IP}:5000" >> .env

grep -q '^GF_SERVER_ROOT_URL=' .env \
  && sed -i "s|^GF_SERVER_ROOT_URL=.*|GF_SERVER_ROOT_URL=http://${PUB_IP}:3001|" .env \
  || echo "GF_SERVER_ROOT_URL=http://${PUB_IP}:3001" >> .env

echo "==> [4] Python venv"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

echo "==> [5] Start postgres + redis + mlflow"

docker compose up -d postgres redis mlflow

echo "==> [6] Wait for MLflow"

python scripts/wait_for_mlflow.py

echo "==> [7] Train model if dataset exists"

if [[ -f data/raw/fraudTrain.csv ]]; then
  python training/train.py
else
  echo "WARN: data/raw/fraudTrain.csv missing"
  echo "Upload Kaggle dataset first, then rerun training/train.py"
fi

if [[ ! -f training/features.parquet ]]; then
  echo "ERROR: training/features.parquet missing"
  exit 1
fi

echo "==> [8] Feast apply"

feast -c feast_repo apply

echo "==> [9] Materialize features"

python scripts/materialize_features.py

echo "==> [10] Start full stack"

docker compose up -d --build

sleep 8

echo "==> Validate API"

api_ok=0
for i in {1..30}; do
  if curl -fsS http://127.0.0.1:8000/health | python -m json.tool; then
    echo "API is healthy"
    api_ok=1
    break
  fi

  echo "Waiting for API health... attempt $i/30"
  sleep 5
done

if [[ "$api_ok" -ne 1 ]]; then
  echo "ERROR: API did not become healthy" >&2
  docker compose logs api --tail=100
  exit 1
fi

echo ""
echo "Deployment completed"
echo ""
echo "Public URLs:"
echo "API:         http://${PUB_IP}:8000/health"
echo "MLflow:      http://${PUB_IP}:5000"
echo "Prometheus:  http://${PUB_IP}:9090"
echo "Grafana:     http://${PUB_IP}:3001"