# Viva / oral exam prep (Phase 14)

Short **questions and model answers** for the ModelServe capstone. Adapt examples to what you actually ran.

---

## A. Architecture & design

**Q: Why Docker Compose on a single EC2 instead of EKS or managed services?**  
**A:** Scope and learning goals: one host reproduces the full path (data → train → registry → features → serve → observe) with minimal cloud surface. Managed DB/KS would hide operational trade-offs we were asked to demonstrate.

**Q: Why Postgres for MLflow and Redis for Feast?**  
**A:** MLflow needs a **transactional** metadata store for experiments and registry (Postgres). Feast’s **online store** is optimized for key-value lookups by entity at low latency (Redis).

**Q: Where does the model run vs where do features come from at request time?**  
**A:** The **sklearn pipeline** runs in the **API container**, loaded **once** from MLflow Production. **Features** for the entity are read via **Feast’s Python SDK** from the **Redis** online store populated by **offline Parquet → materialize**.

---

## B. MLflow

**Q: What is registered as `modelserve_classifier`?**  
**A:** A **sklearn Pipeline** (preprocessing + `RandomForestClassifier`) logged with `mlflow.sklearn.log_model` and transitioned to **Production** after training.

**Q: Why Production stage?**  
**A:** The API resolves `models:/modelserve_classifier/Production` so ops has an explicit “what runs in serving” pointer without hardcoding run IDs.

**Q: What metrics do you log and why?**  
**A:** Accuracy, precision, recall, F1, and ROC-AUC when applicable — to compare runs and document trade-offs on imbalanced fraud data.

---

## C. Feast & `entity_id`

**Q: What is `entity_id` in `POST /predict`?**  
**A:** It is the Feast **entity key** **`cc_num`** (integer). It joins offline/online feature rows for that cardholder context.

**Q: What happens if I send a random `entity_id`?**  
**A:** Feast may return no row → API responds with a **structured error** (missing features), not a fabricated prediction.

**Q: Why not query Redis directly from the API?**  
**A:** Feast provides **schema**, **projections**, and **consistency** between training and serving; bypassing it risks train/serve skew.

---

## D. API & observability

**Q: What Prometheus metrics matter for SLOs?**  
**A:** **`prediction_duration_seconds`** (latency SLO), **`prediction_errors_total`** and ratio to **`prediction_requests_total`** (reliability), **`feast_online_store_*`** (data availability).

**Q: Why scrape every 10s for the API?**  
**A:** Balance between freshness and load; tuned for lab scale (see `monitoring/prometheus/prometheus.yml`).

**Q: Name one alert and what it detects.**  
**A:** Example: **high p95 latency** — histogram quantile over 5m above threshold; indicates overload or slow dependency (Feast/MLflow/disk).

---

## E. CI/CD & infrastructure

**Q: What triggers deploy in GitHub Actions?**  
**A:** **Push to `main`** runs **Deploy (Pulumi + EC2)**: Pulumi **up** on stack **dev**, then **SSH** to run **`deploy_ec2_pipeline.sh`** (Kaggle + **`deploy_ec2.sh`**).

**Q: Which secrets are mandatory?**  
**A:** AWS keys + region, Pulumi token, SSH public/private pair (matching keypair), Kaggle username/key — see [`github-secrets.md`](github-secrets.md).

**Q: How do you tear down AWS resources?**  
**A:** **Actions → Destroy (Pulumi)** (`workflow_dispatch`), or locally **`pulumi destroy`** on stack **dev**. Follow printed hints if IAM state drifts.

---

## F. Limitations & ethics

**Q: Biggest limitation of this capstone?**  
**A:** Single-node, open ports for demo, no PII governance beyond dataset assumptions — not production-ready without hardening.

**Q: Could this model be used for automated blocking of transactions?**  
**A:** Not without calibration, fairness review, override workflows, and regulatory alignment — the stack is a **technical** demo, not a compliance-approved decision system.

---

## G. Quick “curveball” revision

**Q: How would you add A/B testing?**  
**A:** Two Production aliases or weighted routing in front of two model versions; compare **`prediction_requests_total`** by label and business KPIs offline.

**Q: Where would you put drift detection?**  
**A:** Batch scoring of recent features vs training distribution; alert from Prometheus or a scheduled job pushing gauges.

---

For live demo flow, see [`demo-guide.md`](demo-guide.md). For checklist and screenshots, see [`submission-checklist.md`](submission-checklist.md).
