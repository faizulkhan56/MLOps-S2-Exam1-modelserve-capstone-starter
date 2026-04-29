#!/usr/bin/env bash
# Phase 11 — CI/CD pipeline only: Kaggle + dataset prep, then trusted deploy_ec2.sh
# Invoked from GitHub Actions over SSH with env:
#   MODELSERVE_REPO_URL, MODELSERVE_BRANCH (optional), KAGGLE_USERNAME, KAGGLE_KEY
#
# Do not use for ad-hoc laptop deploy; use scripts/deploy_ec2.sh directly there.

set -euo pipefail

REPO="${MODELSERVE_REPO_URL:?MODELSERVE_REPO_URL is required}"
BRANCH="${MODELSERVE_BRANCH:-main}"
ROOT="${MODELSERVE_HOME:-${HOME}/modelserve}"

echo "==> [1] Clone or pull repo into ${ROOT}"

if [[ -d "${ROOT}/.git" ]]; then
  git -C "${ROOT}" fetch --all --prune
  git -C "${ROOT}" checkout "${BRANCH}"
  git -C "${ROOT}" pull --ff-only
else
  mkdir -p "$(dirname "${ROOT}")"
  git clone -b "${BRANCH}" "${REPO}" "${ROOT}"
fi

cd "${ROOT}"

echo "==> [2–3] Kaggle API credentials (~/.kaggle/kaggle.json)"

: "${KAGGLE_USERNAME:?KAGGLE_USERNAME is required}"
: "${KAGGLE_KEY:?KAGGLE_KEY is required}"
export KAGGLE_USERNAME KAGGLE_KEY

mkdir -p "${HOME}/.kaggle"
python3 <<'PY' || { echo "ERROR: could not write kaggle.json" >&2; exit 1; }
import json
import os
from pathlib import Path

cfg = Path.home() / ".kaggle" / "kaggle.json"
cfg.write_text(
    json.dumps(
        {
            "username": os.environ["KAGGLE_USERNAME"],
            "key": os.environ["KAGGLE_KEY"],
        }
    )
)
PY

chmod 700 "${HOME}/.kaggle"
chmod 600 "${HOME}/.kaggle/kaggle.json"

echo "==> [4–6] venv, requirements, kaggle CLI"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# shellcheck source=/dev/null
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install "kaggle>=1.5"

echo "==> [7–8] Download and unzip fraud dataset into data/raw"

mkdir -p data/raw
(
  cd data/raw
  kaggle datasets download -d kartik2112/fraud-detection
  unzip -o fraud-detection.zip
)

echo "==> [9] Limit training rows for CI-friendly run"

export TRAIN_MAX_ROWS=50000

echo "==> [10] Run existing deploy_ec2.sh"

exec bash ./scripts/deploy_ec2.sh
