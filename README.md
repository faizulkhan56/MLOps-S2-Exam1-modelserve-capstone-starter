# ModelServe

> MLOps with Cloud Season 2 — Capstone Exam

<!-- TODO: Write a 2-3 sentence project description -->

## Prerequisites

<!-- TODO: List everything needed to run this project -->

## Quick Start (Local Development)

<!-- TODO: Step-by-step instructions to go from fresh clone to working stack.
     A grader should be able to follow these and have the system running
     in under 15 minutes. -->

## REST Endpoints

<!-- TODO: Fill in this table -->

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | |
| POST | `/predict` | |
| GET | `/predict/<id>?explain=true` | |
| GET | `/metrics` | |

## Environment Variables

<!-- TODO: List all environment variables with descriptions.
     Must match .env.example -->

## GitHub Secrets

<!-- TODO: List all secrets the CI/CD pipeline needs (without values) -->

| Secret | Purpose |
|--------|---------|
| | |

## Engineering Documentation

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full architecture documentation, ADRs, runbook, and known limitations.

## Dataset

[Credit Card Transactions Fraud Detection](https://www.kaggle.com/datasets/kartik2112/fraud-detection) — Simulated credit card transactions generated using Sparkov. Use `fraudTrain.csv` (~1.3M rows, 22 features). Entity key: `cc_num`.

---

*MLOps with Cloud Season 2 — Capstone: ModelServe | Poridhi.io*
