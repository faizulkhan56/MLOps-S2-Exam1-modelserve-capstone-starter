# ModelServe — Demo guide (Phase 13)

Use this checklist for **instructor demos**, **viva**, or **portfolio walkthrough**. Adjust URLs (`localhost` vs **EC2 Elastic IP**) for your environment.

---

## 1. Before the demo (5–10 minutes)

- [ ] Stack running: `docker compose ps` (local) or confirm EC2 + EIP from Pulumi / AWS.
- [ ] Know **one valid `entity_id`** (`cc_num`) from materialized data (see `training/sample_request.json` after train, or query Parquet).
- [ ] Browser tabs ready: **MLflow** `:5000`, **Grafana** `:3001`, **Prometheus** `:9090` targets.
- [ ] Optional: terminal with `curl` history for `/health` and `/predict`.

---

## 2. Storyline (2 minutes)

1. **Problem**: Fraud scoring needs a **consistent model** (MLflow) and **consistent features** (Feast) at request time.
2. **Design**: Single host **Docker Compose** — Postgres + Redis + MLflow + API + Prometheus + Grafana + node-exporter.
3. **Deploy**: **Pulumi** for AWS (VPC, EC2, EIP, S3, ECR); **GitHub Actions** on **push to `main`** runs Pulumi then remote bootstrap script.
4. **Ops**: Prometheus scrapes API metrics; Grafana shows latency, rates, Feast ratio, model version.

---

## 3. Live demo flow (suggested order)

### A. Health and version (30 s)

```bash
curl -s http://<HOST>:8000/health | python -m json.tool
```

**Say:** *Status should be `healthy` after model load; `model_version` shows MLflow Production version.*

### B. Prediction (1 min)

```bash
curl -s -X POST http://<HOST>:8000/predict \
  -H "Content-Type: application/json" \
  -d "{\"entity_id\": <YOUR_CC_NUM>}" | python -m json.tool
```

**Say:** *`entity_id` is the Feast entity `cc_num`. Features come from Redis via Feast SDK; model from MLflow registry.*

### C. Metrics (30 s)

```bash
curl -s http://<HOST>:8000/metrics | head -40
```

**Say:** *Counters/histograms for requests, duration, errors, Feast hits/misses; Prometheus scrapes this every 10s.*

### D. MLflow UI (1 min)

- Open **Experiments** → latest run → metrics / params.
- **Models** → `modelserve_classifier` → **Production** version.

**Say:** *Training registers here; the API loads Production at startup.*

### E. Grafana (2 min)

- Open dashboard **ModelServe — Overview** (provisioned).
- Point at **p50/p95/p99**, **request rate**, **error rate**, **Feast ratio**, **model version** stat/table.

**Say:** *If time permits, generate a few `/predict` calls and refresh to show traffic.*

### F. Prometheus alerts (optional)

- **Alerts** page — rules for latency, error rate, target down.
- **Say:** *Alerts evaluate from the same metrics the dashboard uses.*

### G. CI/CD (1 min — slides or Actions UI)

- Show **Actions** → latest **Deploy (Pulumi + EC2)** run: Pulumi step green → SSH step green.
- Mention secrets from [`github-secrets.md`](github-secrets.md).

---

## 4. Questions you should be ready to answer

| Question | Short answer |
|----------|----------------|
| Why Redis? | Feast **online store** for low-latency feature reads. |
| Why Postgres? | MLflow **tracking** backend store. |
| Why not RDS/EKS? | Capstone scope: **single EC2** + Compose. |
| What if `entity_id` is unknown? | Feast miss / missing features → **structured error**, not a random default score. |
| How do you redeploy code? | **Push `main`** (CI) or **pull + `deploy_ec2.sh`** on the server. |

---

## 5. If something fails during the demo

Jump to [`troubleshooting.md`](troubleshooting.md) sections: **API / Feast**, **MLflow**, **Grafana port**, **CI SSH**.

---

## 6. After the demo

- Do **not** leave default Grafana password in production.
- Optional: run **Destroy** workflow in a sandbox account if tearing down the capstone stack.
