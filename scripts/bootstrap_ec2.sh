#!/usr/bin/env bash
# Phase 10 — EC2 bootstrap verification (runs after Pulumi user-data).
# Idempotent: verifies Docker, Compose plugin, AWS CLI, Git, unzip; ensures ubuntu is in docker group.
set -euo pipefail

if [[ "${EUID:-0}" -eq 0 ]]; then
  echo "Run as ubuntu (not root), e.g.: sudo -u ubuntu $0" >&2
  exit 1
fi

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing: $1" >&2
    exit 1
  }
}

need_cmd docker
docker compose version >/dev/null
need_cmd aws
need_cmd git
need_cmd unzip

if groups | grep -q '\bdocker\b'; then
  echo "OK: user is in docker group"
else
  echo "WARN: user not in docker group — log out and back in, or: sudo usermod -aG docker \"$USER\"" >&2
fi

docker info >/dev/null
echo "OK: bootstrap_ec2.sh verification finished"
