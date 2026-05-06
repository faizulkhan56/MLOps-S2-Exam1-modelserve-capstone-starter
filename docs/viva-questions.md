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

## K. Why Random Forest? Theory, alternatives & classification metrics

### Q: Why did we choose `RandomForestClassifier` for this fraud experiment?

**Short answer:** It is a strong **default for tabular fraud data** in sklearn: handles **numeric + one-hot categoricals** inside our **`Pipeline`**, supports **`class_weight`** for **class imbalance**, outputs **`predict_proba`** (needed for **`fraud_probability`** in the API), is **stable** and **well-supported by MLflow**, and stays within **course complexity** (no extra ML libraries required).

**Expanded — reasons that match *this* codebase:**

| Reason | Detail |
|--------|--------|
| **Tabular fraud** | Transaction features (amount, geo, time, merchant coords, etc.) are **structured columns** — tree ensembles are a standard first-line approach before deep models. |
| **Mixed preprocessing** | [`training/train.py`](../training/train.py) uses **`ColumnTransformer`**: scaled numerics + **one-hot** categoricals. **Tree models do not assume linearity**; they split on thresholds and combine many splits to approximate non-linear boundaries. |
| **Imbalance** | Fraud is **rare**; `RandomForestClassifier(..., class_weight="balanced", ...)` **reweights** samples so the forest pays more attention to the minority class — a simple, explicit lever in code. |
| **Probabilities** | Random forests average **leaf class proportions** across trees → **`predict_proba`** is well-defined; the API exposes **`fraud_probability`** from **`proba[0][1]`** ([`app/main.py`](../app/main.py)). |
| **Robustness** | **Bagging** (many trees on bootstrap samples) **reduces variance** compared to a single **DecisionTree**, which overfits easily. |
| **Scope** | One **`sklearn.ensemble`** import, easy **`mlflow.sklearn.log_model`**, no GPU or separate boosting install — good for a **reproducible MLOps** story (train → register → serve). |

**Honest caveat for viva:** Random Forest is **not guaranteed** to be the best model on this dataset; it is a **sensible baseline**. You can say you would **compare** against **gradient boosting** (XGBoost / LightGBM / CatBoost) in a real project.

---

### Q: How does Random Forest work (brief theory)?

**Short answer:** An **ensemble** of many **decision trees**, each trained on a **bootstrap sample** of rows and using **random subsets of features** at each split; classification **predictions** are **majority vote**, **probabilities** are **averaged tree probabilities**.

**Expanded:**

1. **Decision tree base learner:** Each tree recursively splits data on feature thresholds to minimize impurity (e.g. **Gini**). A single tree can **memorize** noise → **high variance**.

2. **Bagging (Bootstrap AGGregatING):** Train tree \(b\) on a random sample **with replacement** of size \(n\). Repeat for \(B\) trees. **Averaging** predictions reduces variance — the core **Random Forest** idea (Breiman).

3. **Random feature subsets:** At each split, only **`max_features`** (or sqrt of \(p\) by default in sklearn for classification) of the **\(p\)** inputs are considered. That **decorrelates** trees so bagging works better.

4. **Output:** For binary fraud, each leaf has a **fraction** of positive examples; the forest **averages** those fractions → **`predict_proba`**.

5. **Typical strengths:** Good **off-the-shelf** performance on mixed tabular data; **non-linear** interactions; relatively **few critical hyperparameters** compared to neural nets.

6. **Typical weaknesses:** **Slower** inference than linear models if **`n_estimators`** is huge; **memory** for many trees; **less interpretable** globally than one logistic regression (though **feature importances** exist); **high-cardinality** one-hot can make trees expensive — we cap categories (**`max_categories=20`**) in training.

---

### Q: Why not another model class here? (When would others fit or not?)

**Short answer:** Other models **could** fit — the choice is **engineering + pedagogy**, not a proof that RF is optimal. Below is how examiners expect you to argue trade-offs.

| Model family | Why it *could* work | Why we did **not** pick it as the default *here* |
|--------------|---------------------|-----------------------------------------------|
| **Logistic regression** | Fast, **calibrated**-ish scores with **`CalibratedClassifierCV`**, very interpretable **coefficients**. | **Linear** decision surface in **transformed** feature space; fraud boundaries are often **non-linear**; may need **heavy feature engineering** to match tree ensembles. |
| **Gradient boosting** (XGBoost / LightGBM / CatBoost) | Often **state-of-the-art** on **tabular** competitions; strong with defaults + tuning. | **Extra dependency** and tuning surface; course stack emphasizes **sklearn + MLflow**; valid viva answer: *“We’d add boosting as the next experiment.”* |
| **Support Vector Machine** | Worked well in older medium-sized tabular tasks. | **Poor scaling** to large \(n\); **no natural `predict_proba`** unless Platt-style calibration; usually **not** first choice for large fraud CSVs. |
| **Neural networks** | Can learn arbitrary functions. | Tabular fraud often does **not** need them; need **more tuning**, data volume, and infra; **harder to explain** in a capstone viva. |
| **Naive Bayes** | Very fast baseline. | Strong **independence** assumptions rarely hold for transaction features. |
| **KNN** | Simple. | **Inference cost** grows with data; **feature scaling** sensitive; weak default for this use case. |

**One sentence for oral exam:** *We used **RandomForestClassifier** as a **strong sklearn baseline** with **class weights** and **probabilities**; **boosting** would be the next step if metrics plateau.*

---

### Q: Explain the metrics logged in `train.py` — accuracy, precision, recall, F1, ROC-AUC

Metrics are computed on the **held-out test split** and logged to MLflow in [`training/train.py`](../training/train.py) (~lines 207–216). **Binary positive class = fraud (`is_fraud` = 1).**

| Metric | Formula / meaning (binary fraud) | Why it matters here |
|--------|-----------------------------------|---------------------|
| **Accuracy** | \(\frac{TP + TN}{TP + TN + FP + FN}\) — fraction of **correct** predictions. | Easy to read but **misleading** when fraud is **rare**: predicting “all legitimate” can yield **high accuracy** and **zero recall** on fraud. **Never** cite accuracy alone for fraud. |
| **Precision** | \(\frac{TP}{TP + FP}\) — of transactions **flagged** fraud, how many **actually** fraud. | **Cost of false alarms**: blocks, reviews, customer friction. Low precision → too many **false positives**. |
| **Recall** | \(\frac{TP}{TP + FN}\) — of **real** fraud cases, how many we **catch**. | **Cost of missed fraud**: financial loss, regulatory exposure. Low recall → **false negatives**. |
| **F1** | Harmonic mean of precision and recall: \(2 \cdot \frac{precision \cdot recall}{precision + recall}\). | Single **balance** when you care about **both** FP and FN trade-offs; useful for **comparing runs** with one number (still not a substitute for domain cost weights). |
| **ROC-AUC** | Area under **ROC curve**: **TP rate vs FP rate** as **threshold** varies on **`predict_proba`**. | Measures **ranking** ability — does the model **score** fraud higher than non-fraud on average? Logged only when both **`y_test`** and **`pred`** contain **both classes** and enough variation (see `if len(np.unique(y_test)) > 1 and len(np.unique(pred)) > 1` in code); otherwise **ROC-AUC is skipped** (undefined or degenerate). |

**Confusion matrix vocabulary (quick):** **TP** = fraud predicted fraud; **TN** = legit predicted legit; **FP** = legit flagged fraud; **FN** = fraud missed.

**What we do *not* log (but you can mention):** **PR-AUC** (precision–recall curve area) is often **better than ROC-AUC** under **heavy imbalance** because it focuses on the **minority class**. Adding it would be a small extension to `train.py`.

---

### Q: What tuning moves improve these metrics in practice?

**Short answer:** Improve **data** and **model capacity / regularization**, then tune **threshold** on validation data using **business costs** — not only accuracy.

**Concrete levers (overlap with §J):**

1. **Hyperparameters** ([`training/train.py`](../training/train.py) `RandomForestClassifier`): increase **`n_estimators`** (often smoother scores), tune **`max_depth`** / **`min_samples_leaf`** (**variance vs bias**), try **`max_features`** at each split, experiment with **`class_weight`** or manual `{0: w0, 1: w1}` matching **FN vs FP** cost.

2. **More / cleaner data:** env **`TRAIN_MAX_ROWS`** — using **full** Kaggle file usually helps generalization vs a tiny slice.

3. **Preprocessing:** `OneHotEncoder(max_categories=20)` trades **rarity tail** vs noise; imputer **`median`** vs **`mean`** can shift metrics slightly.

4. **Threshold / operating point:** Default sklearn **`predict()`** uses **0.5** on probability — often **suboptimal** for fraud. On a **validation** set, sweep thresholds and plot **precision vs recall**; pick the point your **business** accepts (e.g. minimum recall with precision floor).

5. **Calibration:** If **`fraud_probability`** must align with **true frequencies**, consider **`CalibratedClassifierCV`** wrapping the pipeline or **Platt** scaling — improves **interpretability** of **proba**, not always raw ranking.

6. **Alternative algorithms:** If RF plateaus, **LightGBM/XGBoost** with early stopping and **`scale_pos_weight`** (or sample weights) is a common **next step**.

**Viva one-liner:** *Random Forest gives a **probabilistic**, **imbalance-aware** baseline on **tabular** fraud; we log **precision/recall/F1** and **ROC-AUC** because **accuracy lies** on rare events; **boosting** and **threshold tuning** are the usual upgrades.*

---

## L. Train/test split ratio & model fit (overfitting / underfitting)

### Q: In what ratio do we split train vs test — is it the “most efficient”?

**Short answer:** [`training/train.py`](../training/train.py) uses **`train_test_split(..., test_size=0.2, stratify=y, random_state=RANDOM_STATE)`** → **80% train / 20% test**. That is a **common default**, **not** a universal optimum; “efficiency” depends on **dataset size**, **class balance**, and whether you need **cross-validation** instead of a single split.

**Expanded:**

| Aspect | What this repo does | Why it matters |
|--------|---------------------|----------------|
| **Ratio** | **0.2** test → **80 / 20** | Enough held-out rows for a **stable** estimate of metrics when the Kaggle file is **large**; old rule-of-thumb is **70/30** or **80/20** for single splits. |
| **Stratification** | **`stratify=y`** | Keeps **fraud vs non-fraud** proportions **similar** in train and test — critical for **imbalanced** fraud data so the test set still contains **enough** minority-class examples to measure **recall/precision** meaningfully. |
| **Random seed** | **`random_state=42`** | **Reproducible** splits across runs / laptops / CI. |

**Is 80/20 the “best”?**

- **No single ratio is always best.** With **millions** of rows, **90/10** or **95/5** can still yield a **huge** test set — you might **train on more** data. With **very few** rows (or rare fraud), **20%** test might leave **too few** fraud cases in `y_test` → **noisy** precision/recall — then **k-fold cross-validation** or **stratified K-fold** is better than obsessing over 80/20.
- **Efficiency** in ML usually means **generalization error**, not CPU time: you want a split (or CV) that **estimates production performance** without **using the test set for tuning** (otherwise you **leak** information — treat test as **once** for final reporting, or use a **validation** split inside train for hyperparameter search).

**Viva phrase:** *We use **80/20 stratified** as a **standard, reproducible** holdout; for smaller or messier data we’d switch to **stratified K-fold** or add a **validation** fold for tuning.*

---

### Q: What are overfitting and underfitting? Related ideas for the oral exam

**Short answer:** **Underfitting** = model too **simple** → poor fit on **both** train and test (**high bias**). **Overfitting** = model too **complex** or too **tuned to noise** → great on **train**, worse on **test** (**high variance**). The goal is **good generalization**: similar quality on **unseen** data.

**Definitions (examiner-friendly):**

| Concept | Symptom | Typical cause | Fraud angle |
|---------|---------|----------------|-------------|
| **Underfitting** | **Train** metrics **and** **test** metrics both **low**; predictions look **random** or always majority class. | Model **capacity** too low (e.g. very shallow tree, heavy regularization), **wrong features**, or **bad preprocessing**. | Always predicting **non-fraud** → **high “accuracy”** but **zero recall** on fraud — looks OK until you read **recall**. |
| **Overfitting** | **Train** metrics **much better** than **test**; large **gap**. | **Too many parameters** / deep trees, **too few samples**, **memorizing** noise, or **tuning hyperparameters using the test set** (cheating the metric). | Model **fits quirks** of training merchants/cards; **fails** on new cards — **precision/recall** drop on holdout. |
| **Bias–variance tradeoff** | **Bias** = systematic error (wrong assumptions); **variance** = sensitivity to training sample draw. | Often shown as **U-shaped** total error: simple models **bias↑**, complex models **variance↑**. | Random Forest **averages trees** to **reduce variance** vs one tree; still can overfit if **`max_depth`** unbounded and **`n`** small. |
| **Generalization** | Performance on **new** data from the **same distribution** as training. | Good generalization = train and test metrics **aligned** (small gap). | Production traffic **drifts** → generalization gets worse even without “overfitting” in the classical sense (**concept drift**). |

**Signs in MLflow / `train.py`:** Compare logged **test** metrics across runs. If you logged **train** metrics too (not in this script by default), a **big train–test gap** hints at **overfitting**. If **both** are bad → **underfitting** or **data/label** issues.

**Related terms (quick):**

- **Validation set:** subset used to **tune** hyperparameters — **not** the final test set.
- **Cross-validation:** multiple train/validation folds → **lower variance** estimate of performance than one 80/20 split.
- **Regularization:** constraints that **reduce overfitting** (here: **`max_depth`**, **`min_samples_leaf`**, **`max_features`** in Random Forest; fewer/smaller trees).

**Viva one-liner:** ***Underfitting*** *bad everywhere; **overfitting** great on train, worse on test — we hold out **20% stratified** to see **generalization**, and we’d use **CV** if the dataset were smaller or noisier.*

*Systematic **hyperparameter search** (GridSearchCV, which knobs to turn, and how that fights over/underfitting in this repo) is in **§M** below.*

---

## M. Hyperparameter tuning in ModelServe, overfitting/underfitting & what to do in the lab

### Q: What is hyperparameter tuning, and do we do it automatically in this repo?

**Short answer:** **Hyperparameters** are settings chosen **before** training (**tree depth**, **`n_estimators`**, **`max_features`**, imputer strategy, etc.). **Learned parameters** are **weights / splits** fitted from data. This repo uses **fixed** hyperparameters in [`training/train.py`](../training/train.py) (`RandomForestClassifier(n_estimators=100, max_depth=20, …)` — ~lines 187–194) — there is **no** built-in **`GridSearchCV`**, **`RandomizedSearchCV`**, or **Optuna** loop. “Tuning” today means **you edit numbers** and **re-run** `train.py`, then compare metrics in **MLflow**.

**Expanded — why automate tuning (conceptually):**

- Manual trial-and-error works for a capstone, but **systematic search** explores combinations and reduces **lucky** single runs.
- The **objective** is usually a **validation** metric (e.g. **F1**, **ROC-AUC**) that reflects **business** goals — **not** training loss alone.

---

### Q: Which objects in our pipeline *are* hyperparameters (for viva + for tuning)?

Everything below is **not learned by gradient descent**; sklearn treats these as **constructor arguments** to **`Pipeline`** / **`RandomForestClassifier`** / **`ColumnTransformer`** children:

| Layer | Examples in this lab | Notes |
|-------|----------------------|--------|
| **Random forest** | `n_estimators`, `max_depth`, `min_samples_leaf`, `max_features`, `min_samples_split`, `class_weight`, `random_state` | Main **capacity vs regularization** levers (see table below). |
| **Preprocessing** | `SimpleImputer(strategy="median")`, `OneHotEncoder(max_categories=20)` | Affect **input** to trees; can be included in a search **inside** the same `Pipeline` (prefix params with `prep__` / `clf__`). |
| **Data / split (pseudo-hyperparameters)** | `test_size=0.2`, **`TRAIN_MAX_ROWS`**, `random_state` | Not model params but **change generalization** estimates. |

**Current defaults (memory aid):** `n_estimators=100`, `max_depth=20`, `min_samples_leaf=2`, `class_weight="balanced"`. **`max_features`** is **not passed** → sklearn uses its **classification default** (`"sqrt"` of the number of features at each split).

---

### Q: What is the logic behind our chosen **numbers** for the forest and preprocessing?

**Short answer:** They are **practical teaching defaults**: good baseline quality on tabular fraud, **reasonable train time** on a VM, and **explicit regularization** (depth cap, leaf size, balanced classes, capped one-hot). They are **not** proven optimal until you run **CV** or search.

**Defined in:** [`training/train.py`](../training/train.py) (~165–194).

| Setting | Value | What it does | Logic / trade-off |
|---------|--------|--------------|-------------------|
| **`n_estimators`** | **100** | Number of trees; forest output = **vote** or **average** of tree probabilities. | More trees **smooth** predictions (**lower variance**) but cost **~linear** time. **100** matches common sklearn examples: strong enough before **diminishing returns**; **200–500** is a typical next step if CV gains. |
| **`max_depth`** | **20** | Maximum **depth** of each tree (longest root→leaf path). | **Unbounded** (`None`) can **overfit** noise. **20** limits how “jagged” the decision surface can get — **enough** depth for interaction effects, **not** infinite memorization. |
| **`min_samples_leaf`** | **2** | Minimum **training samples** required in a leaf (splitting stops if it would violate this). | **`1`** allows **singleton** leaves → classic overfit. **`2`** is a **minimal** regularization bump; **`5–20`** would **smooth** more if CV shows overfit. |
| **`class_weight`** | **`"balanced"`** | Weights classes **inversely** to frequency in `y` when building trees. | Fraud is **rare**; without this, trees optimize **overall error** by favoring the majority. **`balanced`** is the standard sklearn fix; **`balanced_subsample`** reweights **per bootstrap** sample. |
| **`max_features`** | **Default** (`"sqrt"` of *p*) | At **each split**, only a **random subset** of input columns is candidates. | This **decorrelates** trees (core RF idea). We **don’t hard-code** it; tuning could try **`"log2"`**, **`0.3`**, or **`None`** (all features every split — often **more correlated** trees). |

**`SimpleImputer(strategy="median")`**

- Fills **missing** numerics with the **per-column median** learned on the **training** portion of each CV fold (when the imputer lives inside **`Pipeline`**, there is **no leakage** from validation rows).
- **Median vs mean:** Transaction amounts and similar fields are **skewed**; outliers **move the mean** more than the **median** → median imputation is **robust** and a standard choice for financial-ish numerics.

**`OneHotEncoder(..., max_categories=20)`**

- **One-hot** encodes categoricals but **limits** how many distinct column levels are kept separately; **tail** categories are grouped (**infrequent** bucket in sklearn).
- **Why 20:** Stops **exploding** dimensionality on high-cardinality columns and reduces **noise splits** on ultra-rare categories — acts as **implicit regularization**. **Cost:** fraud signal tied to **rare** merchants may be **collapsed**; raising the cap is justified only if **validation** says it helps.

---

### Q: How would we *introduce* hyperparameter tuning in this lab (correct workflow)?

**Short answer:** Never tune on **`X_test`**. Either (**A**) **`StratifiedKFold`** cross-validation on **`X_train` only**, or (**B**) split **`X_train`** → **`X_tr` / `X_val`**, search on **`X_tr`**, pick best params, **final fit** on full **`X_train`**, then **one** evaluation on **`X_test`** for reporting. Log **best params** and **metrics** to **MLflow**.

#### Why we must not tune on `X_test`

- **`X_test`** simulates **unseen** production data. If we **choose** hyperparameters because they **maximize test metrics**, those numbers are **optimistically biased** — we have **overfit the test set** (**selection leakage**). Correct story: **tune** with **train (+ CV or val)** only; **report** test **once** (or rarely) as **final** generalization.

#### Path (A): `StratifiedKFold` on `X_train` only

1. Keep the existing split: **`train_test_split(..., test_size=0.2, stratify=y)`** → **`X_train`, `X_test`**.
2. **`GridSearchCV(..., cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42))`** repeatedly **re-partitions** **`X_train`** into 5 parts: train on **4**, score on **1**, rotate. Every training row is used **4** times for training and **1** time as **validation**.
3. **`StratifiedKFold`** preserves **fraud proportion** in each fold — critical when positives are **rare**.
4. **`search.fit(X_train, y_train)`** selects **`best_params_`** maximizing **`scoring`** (e.g. **`roc_auc`**) **averaged** across folds.
5. With **`refit=True`** (default), **`search.best_estimator_`** **re-fits** the **full** **`Pipeline`** on **all** **`X_train`** using **`best_params_`** — that is the model you **log** and optionally **register**.
6. **Then** compute test metrics **once** from **`search.best_estimator_.predict`** / **`predict_proba`** on **`X_test`**.

#### Path (B): nested train / validation / test

1. **`X_train`** → second split **`X_tr`, `X_val`** (stratified).
2. Search hyperparameters using **`X_tr`** only, **select** on **`X_val`**.
3. **Refit** on **`X_train`** (concatenate tr+val) with the winner.
4. **Final** readout on **`X_test`**.

#### Concrete sklearn steps (still **conceptual** — not committed in repo)

1. Instantiate **`Pipeline([("prep", pre), ("clf", RandomForestClassifier(random_state=42))])`** (avoid fixing every `clf` knob in the constructor if the grid will override them).
2. **`param_grid`**: e.g. `{"clf__max_depth": [10, 20, None], "clf__min_samples_leaf": [1, 2, 5], "clf__n_estimators": [100, 200]}` — keys use **`step__param`** syntax.
3. **`search = GridSearchCV(pipeline, param_grid, cv=StratifiedKFold(5, shuffle=True, random_state=42), scoring="roc_auc", n_jobs=-1, refit=True)`** then **`search.fit(X_train, y_train)`**.
4. **MLflow:** `mlflow.log_params(search.best_params_)`, log **`search.best_score_`** (CV mean), then compute test metrics and **`mlflow.sklearn.log_model(search.best_estimator_, ...)`** inside the same run as today’s script.

#### Why **`scoring=`** for fraud

- **`accuracy`** rewards **“always legit”** on imbalanced data. Prefer **`roc_auc`**, **`f1`**, **`average_precision`**, or a **custom** scorer (e.g. **`recall`** if false negatives are unacceptable). Align the scorer with the **business** story (§K).

#### Integrating this into the **ModelServe** lab — practical effects

| Area | What changes |
|------|----------------|
| **Wall time** | Each hyperparameter **combination** × **5 folds** = **many** full pipeline fits; expect **longer** runs than a single `train.py`. |
| **MLflow** | Richer **param** and **metric** history; easy to show **“baseline vs tuned”** in the UI. |
| **Feast / API** | If search only touches **`clf__`**, **Parquet columns** unchanged → **no** Feast schema change. If you search **`prep__`** (imputer, encoder, scaler), **re-export** **`features.parquet`**, **`feast apply`**, **`materialize_features.py`**, **restart API** (§J Plan 3). |
| **Reproducibility** | Fix **`random_state`** on forest, CV **`shuffle`**, and **`numpy`** seeds so results are **repeatable** on the VM. |

**Optional:** **`mlflow.sklearn.autolog()`** or save **`search.cv_results_`** as a **CSV artifact** for the examiner.

---

### Q: Hyperparameter tuning vs overfitting / underfitting — how do we reduce each *in this lab*?

**Concept link:** **Tuning** searches hyperparameters that control **model complexity** and **regularization**. **Overfitting** ≈ **too complex** for the data; **underfitting** ≈ **too simple** or **wrong setup**.

| Problem | What you see | Hyperparameters / actions **in ModelServe** that typically **help** |
|---------|----------------|----------------------------------------------------------------------|
| **Overfitting** | Train metrics **much better** than test; unstable trees. | **Lower** `max_depth`; **raise** `min_samples_leaf` / `min_samples_split`; **lower** `max_features` (more randomness per split); **fewer** trees only helps slightly — focus on **depth/leaf** first; **more training data** (`TRAIN_MAX_ROWS` unset = full file); **stratified CV** so you don’t pick params that **lucky-fit** one split. |
| **Underfitting** | **Both** train and test metrics **low**; model barely beats baseline. | **Higher** `max_depth` (until overfit); **more** `n_estimators`; **relax** `min_samples_leaf` (careful — can overfit); richer **features** (schema + Feast — avoid skew); check **`class_weight`** and **imbalance** handling. |
| **Metric misleading** | Great test number after **many** manual tweaks using the **same** test set. | **Data leakage:** tune only with **CV on train** or a **validation** set; keep **`X_test`** **untouched** until final comparison — same rule if you add Optuna. |

**Preprocessing levers (same file):** **`OneHotEncoder(max_categories=20)`** — lowering categories can **regularize** (less sparse noise); raising can **underfit** if signal was in dropped tails.

**Operational reminder:** After any winning **`Pipeline`**, still **re-export** **`features.parquet`**, **`feast apply`**, **materialize**, **restart API** if features or preprocessing changed (§J Plan 3).

---

### Q: *(Extra)* Grid search vs randomized search vs Bayesian optimization?

**Short answer:** They differ in **how** they pick the next hyperparameter combinations to try: **grid** = try **every** cell in a discrete table; **random** = try **random** draws from distributions; **Bayesian** = use **past** trial results to **suggest** promising regions. For this capstone, **grid or random + StratifiedKFold** is enough; **Optuna** shines when each trial is **expensive** or the space is **large**.

**GridSearchCV (exhaustive grid)**

- **What it is:** You list **finite** values per parameter (e.g. `max_depth ∈ {10, 20, None}`). Sklearn trains **every combination** (Cartesian product) × **each CV fold**.
- **Pros:** **Complete** coverage of that small grid; **deterministic** given seed; easy to explain in viva.
- **Cons:** **Curse of dimensionality** — 5 params with 4 values each → **4⁵ = 1024** configs × 5 folds; **wasteful** if many combos are obviously bad.
- **When to use here:** **2–4** forest hyperparameters with **2–3** levels each on the Poridhi VM.

**RandomizedSearchCV**

- **What it is:** You define **distributions** (e.g. `max_depth` uniform from 5–40, `n_estimators` from {50,100,200,400}); each trial **samples** one combo; run **`n_iter`** trials.
- **Pros:** Explores **wide** ranges without exploding the budget; often finds **good** regions faster than a **sparse** grid.
- **Cons:** Might **miss** a narrow optimum unless **`n_iter`** is large; less **systematic** than full grid on tiny spaces.
- **When to use here:** You want to sweep **`max_depth`** continuously or try many **`n_estimators`** without a full grid.

**Bayesian optimization (e.g. Optuna, Hyperopt, skopt)**

- **What it is:** Builds a **probabilistic surrogate** of “metric vs hyperparameters” and picks the next point to **maximize expected improvement** (or similar). **Sequential**: trial **t+1** uses outcomes from trials **1…t**.
- **Pros:** **Sample-efficient** when one training run is **minutes/hours**; handles **conditional** spaces (e.g. only tune `max_depth` if `criterion=…`) well in Optuna.
- **Cons:** More **moving parts** (storage backend, pruners); overkill if sklearn grid finishes in **minutes**.
- **When to use here:** Extra credit / thesis flavor — “we plugged **Optuna** into `train.py` and logged trials to MLflow.”

**Lab recommendation:** **`GridSearchCV` + `StratifiedKFold(5)`** on **`RandomForestClassifier`** with a **small** grid is the clearest **exam narrative**. Upgrade to **`RandomizedSearchCV`** if the grid is too big; use **Optuna** only if you need **efficiency** on a huge space or **early stopping** (pruning) per fold.

---

**Viva one-liner:** *Hyperparameters are the **knobs** on `RandomForestClassifier` and preprocessing; this repo **fixes** them — real tuning uses **CV on train** and **`GridSearchCV`/`RandomizedSearchCV`**, logs **`best_params_`** to MLflow, then evaluates **once** on the held-out **20%**; **shallow trees / larger leaves** fight **overfitting**, **deeper / more trees** can fix **underfitting** until the gap widens.*

---

For live demo flow, see [`demo-guide.md`](demo-guide.md). For screenshots and submission expectations, see [`submission-checklist.md`](submission-checklist.md).
