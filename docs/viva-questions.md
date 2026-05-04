# Viva / oral exam prep (Phase 14)

**Questions, expanded answers, and extra “unseen” prompts** for the ModelServe capstone. Adapt examples to what you actually ran (local VM vs EC2, times, run IDs).

**Related:** [`demo-guide.md`](demo-guide.md), [`submission-checklist.md`](submission-checklist.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`explanation-linewise.md`](../explanation-linewise.md).

---

## A. Architecture & design

### Q: Why Docker Compose on a single EC2 instead of EKS or managed services?

**Short answer:** Scope and learning goals — one host reproduces **data → train → registry → features → serve → observe** with minimal cloud surface and inspectable failure modes.

**Expanded:**

- **EKS** would add control plane cost, manifests, ingress, and storage classes — most of that is **operations theatre** for this rubric, not the ML lifecycle story you are graded on.
- **Managed RDS / ElastiCache** reduce “day 2” work but **hide** the explicit split this capstone wants: **Postgres for MLflow metadata** vs **Redis for Feast online lookups**.
- **Single EC2 + Compose** matches how many teams **prototype** production: same Compose file locally and on the server, easy logs (`docker compose logs`), single security group to reason about.
- **Trade-off you should name in viva:** no horizontal scaling, no AZ failover — you would add an ALB + ASG + managed Redis for real production.

---

### Q: Why Postgres for MLflow and Redis for Feast?

**Short answer:** MLflow needs a **transactional** metadata store for experiments and the **model registry**; Feast’s **online store** is optimized for **low-latency key-value** reads by **entity** at inference time.

**Expanded:**

- **Postgres** gives ACID semantics for run lineage, parameters, metrics, and registry stages (**Staging / Production**). The MLflow server uses `postgresql://…` as `--backend-store-uri`.
- **Redis** (here with AOF persistence) stores **entity-keyed** feature rows that Feast serves via **`get_online_features`**. The API does not hand-roll Redis keys — it goes through Feast so **names and types** stay aligned with the feature view.
- If someone asks “why not Postgres for online features?” — feasible at small scale, but Redis is the **default pattern** in Feast docs for online latency and simple eviction/TTL stories; this repo follows that split.

---

### Q: Where does the model run vs where do features come from at request time?

**Short answer:** The **sklearn Pipeline** runs **inside the API container**, loaded **once** at startup from **MLflow Production** (`models:/modelserve_classifier/Production`). **Features** for the request’s entity come from **Feast’s Python SDK** reading the **Redis** online store, after offline Parquet was **materialized**.

**Expanded:**

- **Model location:** Not re-downloaded per request — startup **`load_model`** (pattern in `api/` code) keeps latency predictable.
- **Feature location:** Not recomputed from raw CSV at inference — they were **prepared in training**, written to **Parquet**, registered in Feast, then **materialized** into Redis for entities you chose to export.
- **Demo sentence:** “Inference combines **two sources of truth**: MLflow says **which weights**, Feast says **which feature vector** for this `cc_num`.”

---

### Q: *(Extra)* What is the blast radius if the EC2 instance dies?

**Answer:** **Total** for this architecture: API, Redis, MLflow UI, and Grafana on that host all disappear until you restore or redeploy. **Pulumi + user-data** can recreate the VM, but **Redis and MLflow volumes** on the instance are not magically multi-AZ — you would need backups, S3 for artifacts only, and rerun train/materialize unless you restore volumes. This is a **known limitation**, not a bug.

---

### Q: *(Extra)* Why is MLflow on HTTP and exposed on port 5000 in the security group?

**Answer:** **Course/demo convenience** — you need browser access to the MLflow UI from your laptop. In production you would put MLflow **behind VPN or SSO**, **TLS** termination at ALB, and **restrict ingress** to corporate IPs. Naming this shows you understand **defense in depth** beyond the capstone.

---

## B. MLflow

### Q: What is registered as `modelserve_classifier`?

**Short answer:** A **scikit-learn Pipeline** (preprocessing steps + **`RandomForestClassifier`**) logged with **`mlflow.sklearn.log_model`** and transitioned to **Production** after training.

**Expanded:**

- The **registry name** is how the API resolves **`models:/modelserve_classifier/Production`** without hardcoding a run UUID.
- The **artifact** includes the **full pipeline** (encoders + model), so inference uses the **same** transformations as training — critical when you add categoricals or scaling.

---

### Q: Why Production stage?

**Short answer:** The API is wired to **Production** so operations has a single, explicit pointer to **what runs in serving**; you can keep **Staging** for experiments without breaking live behavior.

**Expanded:**

- **Alternative anti-pattern:** embedding **run_id** in config — works but forces redeploy for every experiment winner.
- **MLflow stages** are **conventions** — your CI could automate **transition** after tests pass; here it is often manual or script-driven after `train.py`.

---

### Q: What metrics do you log and why?

**Short answer:** **Accuracy, precision, recall, F1**, and **ROC-AUC** where applicable — to compare runs on **imbalanced** fraud data and justify threshold choices.

**Expanded:**

- On fraud data, **accuracy alone** is misleading (majority class dominates). **Recall** ties to “catch fraud”; **precision** to “false alarms”.
- In viva, tie metrics to **business cost**: false negatives vs false positives — even if you did not implement cost-sensitive learning.

---

### Q: *(Extra)* Where do MLflow **artifacts** live vs **registry metadata**?

**Answer:** **Metadata** (run name, metrics, model version record) is in **Postgres**. **Large artifacts** (pickled model, conda env info) are stored in the **artifact store** — in this repo, the MLflow server is configured to **serve artifacts** from **`/mlflow/artifacts`** on the container volume so clients uploading from the **host** use HTTP instead of trying to write **`file:`** paths inside the container. If training logs **`PermissionError` on `/mlflow`**, the fix is exactly this **`--serve-artifacts`** pattern (see README).

---

## C. Feast & `entity_id`

### Q: What is `entity_id` in `POST /predict`?

**Short answer:** The Feast **entity key** **`cc_num`** (integer) — it joins offline and online feature rows for that cardholder **context**.

**Expanded:**

- Feast **requires** an entity to anchor features in time and identity; here the dataset’s natural key is **`cc_num`**.
- The JSON field is named **`entity_id`** in the API for a **stable HTTP contract** even if the underlying column name in Parquet is `cc_num`.

---

### Q: What happens if I send a random `entity_id`?

**Short answer:** Feast may return **no row** for that key → the API responds with a **structured error** (missing features), **not** a fabricated prediction.

**Expanded:**

- This avoids **silent failure** — returning a default score for unknown entities would be dangerous in fraud (you would lie about confidence).
- **Demo tip:** Use **`training/sample_request.json`** after a successful train — those IDs exist in **`features.parquet`** and Redis after materialize.

---

### Q: Why not query Redis directly from the API?

**Short answer:** Feast provides **schema**, **typed projections**, and **train/serve consistency**; bypassing it risks **train/serve skew** and brittle key naming.

**Expanded:**

- **Train/serve skew** means training used column order **X** but inference accidentally used **Y** — subtle bugs with identical accuracy on a slide but wrong decisions live.
- Feast also lets you **swap online backends** (Redis → something else) without rewriting the API — only config/repo path changes.

---

### Q: *(Extra)* How “fresh” are online features?

**Answer:** As fresh as your last **`materialize_features.py`** (and Feast TTL settings if you set any). This capstone is **batch** materialization, **not** streaming — if examiners ask about real-time fraud, you say: “We’d add stream ingestion + shorter materialization windows or online transforms — out of scope here.”

---

### Q: *(Extra)* What is `feast apply` doing?

**Answer:** It registers or updates **feature definitions** (entities, feature views, data sources) in the Feast registry so **`get_online_features`** knows **which columns** to pull from the **online store** for a given **entity list**. It does **not** by itself load all training rows into Redis — that is **`materialize`** / your materialize script.

---

## D. API & observability

### Q: What Prometheus metrics matter for SLOs?

**Short answer:** **`prediction_duration_seconds`** (latency SLO), **`prediction_errors_total`** vs **`prediction_requests_total`** (reliability), and Feast-related counters if exposed (e.g. online store hit/miss) for **data availability**.

**Expanded:**

- **Duration histogram** supports **p50/p95/p99** in Grafana; alerts use **p95 > 2s** over 5m in this repo’s **`alerts.yml`**.
- **Error ratio** catches dependency failures (Feast down, bad payloads) even when some requests succeed.
- Always mention **three pillars** briefly: **metrics** (Prometheus), **logs** (`docker compose logs api`), **traces** (not implemented here — OpenTelemetry would be the upgrade path).

---

### Q: Why scrape every 10s for the API?

**Short answer:** Balance **freshness** vs **load**; API job overrides global **15s** in [`monitoring/prometheus/prometheus.yml`](../monitoring/prometheus/prometheus.yml).

**Expanded:**

- At lab traffic, 10s is **fine**; at high QPS you might **reduce scrape frequency** or use **Pushgateway** for batch jobs — not needed here.
- **node-exporter** stays at **15s** because host metrics change slower than per-request API latency.

---

### Q: Name one alert and what it detects.

**Short answer:** **`ModelServeHighPredictionLatencyP95`** — PromQL **`histogram_quantile(0.95, …)`** on **`prediction_duration_seconds`** over **5m** &gt; **2** seconds → suggests overload, slow Feast/Redis, or CPU starvation.

**Expanded:**

- **`ModelServeAPIDown`:** **`up{job="modelserve-api"} == 0`** → Prometheus cannot scrape **`/metrics`** — API crash or network split.
- **`ModelServeHighPredictionErrorRate`:** errors / requests &gt; **10%** — misconfiguration or upstream failures.

---

### Q: *(Extra)* What does `/health` tell you that `/metrics` does not?

**Answer:** **Health** is a **domain-level** check: is the process up and is the **Production model** loaded (and optionally dependencies reachable)? **Metrics** expose **time series** for aggregating SLIs over many requests. You need **both** — Kubernetes uses similar split (liveness vs RED metrics).

---

## E. CI/CD & infrastructure

### Q: What triggers deploy in GitHub Actions?

**Short answer:** **Push to `main`** runs **Deploy (Pulumi + EC2)**: Pulumi **`up`** on stack **`dev`**, then **SSH** runs **`deploy_ec2_pipeline.sh`** (Kaggle + **`deploy_ec2.sh`**).

**Expanded:**

- **Branch protection** in real teams would require PR review — state what you actually used.
- **Concurrency group** `deploy-main` ensures **overlapping pushes** do not corrupt sequential deploys (`cancel-in-progress: false` means a second run **waits**, good for Pulumi state).

---

### Q: Which secrets are mandatory?

**Short answer:** AWS keys + region, Pulumi token, **matching** SSH public/private pair, Kaggle username/key — see [`github-secrets.md`](github-secrets.md).

**Expanded:**

- **Public key** goes into Pulumi config → **EC2 `authorized_keys`**; **private key** is used by Actions to **SSH/SCP** after the instance exists. **Mismatch** = deploy fails at “run pipeline on EC2”.
- **`PULUMI_CONFIG_PASSPHRASE`** only if your stack config is encrypted.

---

### Q: How do you tear down AWS resources?

**Short answer:** **Actions → Destroy (Pulumi)** (`workflow_dispatch`), or locally **`pulumi destroy`** on stack **`dev`**. If state drifts, use **`pulumi state delete`** on URNs from logs.

**Expanded:**

- **S3 bucket** uses **`force_destroy`** in IaC for teaching cleanup — understand this is **dangerous** for real data buckets.
- **ECR** images may block destroy if retention policies exist — empty repos if needed.

---

### Q: *(Extra)* What does Pulumi create in AWS?

**Answer:** At minimum (see `infrastructure/__main__.py`): **VPC**, **Internet Gateway**, **public subnet**, **route table**, **security group** (SSH + app ports), **EC2 t3.medium** (Ubuntu 22.04), **Elastic IP**, **S3** artifact bucket, **ECR** repositories. **Region** pinned to **`ap-southeast-1`** in code and workflow config.

---

### Q: *(Extra)* Why wait for `docker info` on EC2 after `pulumi up`?

**Answer:** Pulumi returns when the instance is **running**, but **cloud-init** user-data may still be **installing Docker**. The workflow **polls SSH** until **`sudo docker info`** succeeds so **`deploy_ec2_pipeline.sh`** does not race the bootstrap.

---

## F. Limitations & ethics

### Q: Biggest limitation of this capstone?

**Short answer:** **Single-node** topology, **open ingress** for demo, **no** full PII governance — **not** production-ready without hardening, HA, and policy controls.

**Expanded:**

- Add **private subnets**, **bastion**, **TLS**, **secrets manager**, **backup/DR**, and **access logs** for a serious deployment.

---

### Q: Could this model be used for automated blocking of transactions?

**Short answer:** **Not** without **calibration**, **fairness review**, **human override**, and **regulatory** alignment — this stack demonstrates **technical** MLOps, not a **compliance-approved** decision system.

**Expanded:**

- Mention **bias** in historical fraud labels, **demographic parity**, and **right to explanation** where applicable.

---

### Q: *(Extra)* Is storing `cc_num` as an entity ethical?

**Answer:** In **real** systems, raw PAN is **PCI-scoped** — you would tokenize or hash. The **Kaggle dataset** is a teaching artifact; in viva, say you would **never** log raw card numbers to stdout in production and would use **vaulted tokens** as entity IDs.

---

## G. Quick “curveball” revision

### Q: How would you add A/B testing?

**Short answer:** Two **registry** versions or aliases (**Production** vs **Champion**), or routing layer sends **traffic fractions** to two API deployments; compare **`prediction_requests_total`** by **label** and offline KPIs.

**Expanded:**

- Feast must serve **compatible** feature rows for both models, or you version **feature views** alongside models.

---

### Q: Where would you put drift detection?

**Short answer:** **Offline** jobs comparing recent feature distributions to training **reference**; push **gauges** to Prometheus or alert from **batch** results; optionally **evidently** / **great_expectations** on Parquet slices.

**Expanded:**

- **Label drift** needs delayed labels — harder for fraud; **covariate drift** in inputs is easier to monitor first.

---

### Q: *(Extra)* How would you blue/green the API only?

**Answer:** Two target groups or two Compose stacks on **different ports** behind **nginx/traefik**, switch traffic by **weight**; **Redis and MLflow** might stay shared until you split them. Requires **health checks** and **session stickiness** if you had state (you mostly don’t).

---

## H. Training vs inference (favorite examiner angle)

### Q: *(Extra)* Walk through one row from training CSV to `/predict` response.

**Answer (talk track):** Raw CSV → **`train.py`** cleans and builds the sklearn **Pipeline** → logs metrics → **`log_model`** → **Production** → exports **`features.parquet`** with **`cc_num`** as entity → **`feast apply`** registers definitions → **`materialize`** loads Redis → at inference, client sends **`entity_id`** → Feast returns **numeric features** for that **`cc_num`** → API fills **categorical** defaults the pipeline still expects → **`predict_proba`** → JSON with **probability** and **timestamps**.

---

## I. Observability deep cuts

### Q: *(Extra)* Why node-exporter?

**Answer:** **USE** method for the host: CPU, memory, disk — correlates “API slow” with **disk full** or **CPU pegged** vs application-only metrics.

---

### Q: *(Extra)* What is missing for “production” observability?

**Answer:** **Structured logging** aggregation (ELK/Loki), **distributed tracing**, **SLO burn rates**, **on-call paging** (PagerDuty), **runbooks** wired from alerts — this repo stops at **Prometheus + Grafana** for scope.

---

## J. Tuning: changing probabilities & improving inference quality

### Q: Which parameters can we tune so that `fraud_probability` or the prediction changes, and where in the codebase (or outside it) do we change them?

**Short answer:** **`fraud_probability`** is **`predict_proba` class-1** from the **sklearn Pipeline** loaded from MLflow; it changes if the **model** or the **input feature row** changes. **Improve quality** mainly in **`training/train.py`** (data, split, preprocessing, **RandomForest** hyperparameters) and keep **train/serve** alignment via **`training/feature_schema.py`**, **Feast export**, and **`app/main.py`** defaults. **Environment** (`.env`) controls **how much data you train on** and **which registry model** the API loads.

**What the API does today (so you know what “tuning” means):**

- [`app/main.py`](../app/main.py) calls `model_loader.predict(X)`; **`fraud_probability`** is `float(proba[0][1])` — the **positive-class probability** for fraud.
- **`prediction`** is the **argmax / 0.5 default** from sklearn’s `predict()` (standard **0.5 threshold** for `RandomForestClassifier` in binary case). There is **no separate `FRAUD_THRESHOLD` env var** in this repo; changing the **business threshold** (e.g. flag only if proba &gt; 0.7) would be a **new code path** in `main.py` if you add it.

---

### Plan 1 — Change model quality & probability calibration (retrain)

These affect **both** train-time metrics and live **`fraud_probability`** after you register a new **Production** model and restart the API.

| What | Where | Effect |
|------|--------|--------|
| **RandomForest hyperparameters** | [`training/train.py`](../training/train.py) — `RandomForestClassifier(...)` (~lines 187–194): `n_estimators`, `max_depth`, `min_samples_leaf`, `class_weight`, `max_features`, etc. | Stronger/weaker fit, different **probability margins**; `class_weight="balanced"` already mitigates imbalance — try **`balanced_subsample`** or manual weights if you study cost asymmetry. |
| **Random seed** | Same file: `RANDOM_STATE = 42` and split `random_state` | Reproducibility; different seeds → slightly different trees and **probas**. |
| **Train/test split** | `train_test_split(..., test_size=0.2, stratify=y, ...)` | More **test** data → different reported metrics; does not change the fitted model unless you also change **training rows**. |
| **Amount of training data** | Env **`TRAIN_MAX_ROWS`** (read in `_nrows()` / `load_raw()` in `train.py`) | Fewer rows → often **worse** generalization and noisier scores; **full file** usually better if runtime allows. |
| **Preprocessing** | `train.py`: `SimpleImputer(strategy="median")`, `StandardScaler()`, `OneHotEncoder(..., max_categories=20)` | Different encoding/imputation → different **`X`** entering the forest → different **probas**. |
| **Feature set** | [`training/feature_schema.py`](../training/feature_schema.py) — `FEAST_NUMERIC_FEATURE_COLS`; plus categorical columns listed in `train.py` (`cat_cols`) | Adding/removing features requires **syncing Feast** ([`feast_repo/feature_definitions.py`](../feast_repo/feature_definitions.py)), **re-export Parquet**, **`feast apply`**, **`materialize_features.py`**, and ensuring the API row order still matches the pipeline (see Plan 3). |

**After any training change:** run **`train.py`** → new MLflow version → **Production** transition (script does this) → **`docker compose up -d --build api`** (or restart API) so [`app/model_loader.py`](../app/model_loader.py) reloads **`models:/${MLFLOW_MODEL_NAME}/${MLFLOW_MODEL_STAGE}`**.

---

### Plan 2 — Change scores without retraining (same model, different inputs)

| What | Where | Effect |
|------|--------|--------|
| **Feature values for an entity** | **Feast / Redis** — online row comes from **`training/features.parquet`** via **`scripts/materialize_features.py`** | Same `cc_num`, but if you **re-materialize** after updating Parquet, **numeric features** in Redis change → **`fraud_probability`** changes. |
| **Default categoricals at inference** | [`app/main.py`](../app/main.py) — `_CAT_DEFAULTS` / `_CAT_ORDER` (`category`, `state`, `gender` = `"unk"`) | Feast only supplies **numeric** columns; the API **injects** string defaults for categoricals the pipeline was trained with. Changing defaults changes the **one-hot** input → changes **proba**. **Keep aligned with training `fillna("unk")`** unless you intentionally change both train and serve. |
| **Which model version is served** | `.env` / compose: **`MLFLOW_MODEL_NAME`**, **`MLFLOW_MODEL_STAGE`** ([`app/model_loader.py`](../app/model_loader.py)) | Pointing to **Staging** vs **Production** loads a **different artifact** → different scores for the same features. |

---

### Plan 3 — Avoid “improving” train but breaking serve (train/serve skew)

If you change **column lists** or **preprocessing**:

1. Update **`training/train.py`** and **`training/feature_schema.py`** consistently.
2. Update **`feast_repo/feature_definitions.py`** and run **`feast -c feast_repo apply`**.
3. Regenerate **`training/features.parquet`** and run **`python scripts/materialize_features.py`**.
4. Confirm [`app/feature_client.py`](../app/feature_client.py) / [`main.py`](../app/main.py) **column order** still matches the sklearn **`ColumnTransformer`** + pipeline expectations (`_build_model_frame`).

Otherwise probabilities may look “better” offline but **fail or drift** online.

---

### Plan 4 — Optional product-level change (not implemented): custom fraud threshold

To change **`prediction`** (0/1) **without** changing the underlying **`fraud_probability`** distribution, you would add logic such as: *if `fraud_probability >= T` then fraud*, with **`T`** from env (e.g. `FRAUD_THRESHOLD=0.7`). That lives naturally in **[`app/main.py`](../app/main.py)** after `predict_proba`. Today the repo uses sklearn’s default **`predict()`** for **`prediction`**, which is consistent with **0.5** for RF.

---

**Viva one-liner:** *Probability comes from the **loaded MLflow model** and the **feature row** (Feast numerics + API categorical defaults). **Improve** by retraining and hyperparameters in **`train.py`**; **shift live scores** by **materialized features** and **defaults** in **`main.py`**; **avoid skew** by keeping **schema, Feast, and Parquet** in lockstep.*

---

For live demo flow, see [`demo-guide.md`](demo-guide.md). For screenshots and submission expectations, see [`submission-checklist.md`](submission-checklist.md).
