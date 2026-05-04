# Capstone submission checklist (Phase 14)

Use this before **submission**, **demo day**, or **portfolio packaging**.

---

## 1. Screenshots checklist

Capture these for your report or slide deck (placeholder filenames are suggestions).

| # | What to capture | Suggested filename |
|---|-----------------|-------------------|
| 1 | **Docker Compose** — `docker compose ps` showing core services up | `compose-ps.png` |
| 2 | **MLflow UI** — Experiments list + one run with metrics | `mlflow-experiment.png` |
| 3 | **MLflow Models** — `modelserve_classifier` with **Production** stage | `mlflow-registry.png` |
| 4 | **FastAPI `/health`** — browser or terminal JSON (`healthy`, real `model_version`) | `api-health.png` |
| 5 | **`POST /predict`** — successful JSON (`prediction`, `fraud_probability`, `model_version`) | `api-predict.png` |
| 6 | **Prometheus** — `/targets` with `modelserve-api` and `node-exporter` **UP** | `prometheus-targets.png` |
| 7 | **Prometheus** — `/alerts` or Rules page showing loaded alerting rules | `prometheus-alerts.png` |
| 8 | **Grafana** — ModelServe overview dashboard (latency / rate / errors / Feast ratio) | `grafana-dashboard.png` |
| 9 | **GitHub Actions** — successful **Deploy (Pulumi + EC2)** run (green checks) | `gha-deploy.png` |
| 10 | **AWS** — EC2 instance + Elastic IP (optional, blur account IDs if sharing publicly) | `aws-ec2.png` |

**Tips:** Use consistent browser zoom; redact secrets, keys, and internal URLs if posting publicly.

---

## 2. Demo script (10–15 minutes)

| Step | Action | What to say (one line) |
|------|--------|-------------------------|
| 1 | Show repo structure (`app/`, `training/`, `feast_repo/`, `monitoring/`, `infrastructure/`) | “Training, serving, feature store, and observability live in one composable layout.” |
| 2 | `docker compose ps` or AWS EC2 + Compose | “Runtime is Docker Compose on one host for simplicity and reproducibility.” |
| 3 | MLflow UI — Production model | “The API loads `modelserve_classifier` from the registry at startup.” |
| 4 | `curl /health` then `curl /predict` with a valid `entity_id` | “`entity_id` is Feast’s `cc_num`; features come from Redis via Feast SDK.” |
| 5 | `curl /metrics` — point at prediction counters/histogram | “These are what Prometheus scrapes every 10 seconds.” |
| 6 | Grafana dashboard — p50/p95/p99, error rate, Feast ratio | “Dashboard ties inference latency to business and data-quality signals.” |
| 7 | (Optional) GitHub Actions deploy run | “Push to `main` runs Pulumi then remote bootstrap with Kaggle + deploy script.” |

Extended speaking notes: [`demo-guide.md`](demo-guide.md).

---

## 3. Expected `curl` outputs (shape)

Replace `<ID>` with an integer `cc_num` present after train + materialize (see `training/sample_request.json`).

### Health (after model loaded)

```bash
curl -s http://localhost:8000/health
```

**Expected shape** (values vary):

```json
{
  "status": "healthy",
  "model_version": "3"
}
```

If model failed to load: `"status": "degraded"`, `"model_version": "not_loaded"`, optional `"detail"`.

### Predict

```bash
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d "{\"entity_id\": <ID>}"
```

**Expected shape:**

```json
{
  "entity_id": 1234567890123456,
  "prediction": 0,
  "fraud_probability": 0.12,
  "model_name": "modelserve_classifier",
  "model_version": "3",
  "timestamp": "2026-01-15T12:00:00.000000+00:00"
}
```

On missing Feast row, expect HTTP **404** and JSON `error.code` such as `missing_features`.

### Metrics (snippet)

```bash
curl -s http://localhost:8000/metrics | head -30
```

**Expect** lines including `prediction_requests_total`, `prediction_duration_seconds_bucket`, `prediction_errors_total`, `feast_online_store_hits_total`, `model_version_info`, etc.

---

## 4. Model metrics explanation (training)

`training/train.py` logs to MLflow (example metrics — exact numbers depend on data and split):

| Metric | Meaning |
|--------|---------|
| **accuracy** | Fraction of correct class labels on holdout. |
| **precision** | Of predicted frauds, how many were true fraud (trade-off with recall). |
| **recall** | Of true frauds, how many were caught. |
| **f1** | Harmonic mean of precision and recall. |
| **roc_auc** | Discrimination ability of predicted probabilities (when both classes exist). |

**Say in viva:** *We log these per run for comparison; Production promotion uses your registry policy (here: latest version moved to Production after train).*

---

## 5. Monitoring explanation

| Layer | What it does |
|-------|----------------|
| **FastAPI `/metrics`** | Exposes Prometheus-format counters (requests, errors), histogram (latency), Feast hit/miss, model version gauge. |
| **Prometheus** | Scrapes API every **10s**, node-exporter every **15s**; evaluates **alert rules** (p95 latency, error rate, target down). |
| **Grafana** | File-provisioned datasource + **ModelServe overview** dashboard: p50/p95/p99, request rate, error rate, Feast hit ratio, model version. |
| **node-exporter** | Host CPU/mem/disk signals for correlation (not a substitute for app-level SLOs). |

---

## 6. Known limitations (honest list)

- **Single-node** Compose — no HA, no autoscaling; EC2 is one failure domain.
- **Security groups** open required ports broadly for lab demo — production would restrict CIDRs + TLS + auth.
- **No canary / progressive delivery** — new model = manual or scripted redeploy.
- **Feast online store** matches materialized keys — cold entities return errors, not imputed features.
- **Private GitHub repos** need extra clone credentials on EC2 (default pipeline assumes public clone URL).
- **IAM / Pulumi** — historical stacks may need manual state cleanup if resources drifted (see [`troubleshooting.md`](troubleshooting.md)).

---

## 7. Future improvements

| Area | Idea |
|------|------|
| **Serving** | Blue/green or rolling API deploy; load balancer + TLS termination. |
| **Data** | Scheduled Feast materialization; feature validation / Great Expectations. |
| **ML** | A/B tests in MLflow; shadow traffic; drift detection. |
| **Infra** | OIDC for GitHub→AWS; separate staging stack; S3 artifact lifecycle. |
| **Security** | Network segmentation, secrets manager, least-privilege IAM, private ECR pull via instance role (if reintroduced). |

---

## 8. Related docs

| Doc | Use |
|-----|-----|
| [`final-runbook.md`](final-runbook.md) | Commands & cleanup |
| [`troubleshooting.md`](troubleshooting.md) | Errors & fixes |
| [`architecture-summary.md`](architecture-summary.md) | One-page architecture |
| [`viva-questions.md`](viva-questions.md) | Oral prep |
