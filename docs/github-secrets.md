# GitHub Actions secrets (Phases 11–12)

Configure these in the repository: **Settings → Secrets and variables → Actions → New repository secret**.

## Required secrets

| Secret | Used by | Purpose |
|--------|---------|---------|
| `AWS_ACCESS_KEY_ID` | `deploy.yml`, `destroy.yml` | IAM user/role key for Pulumi AWS provider |
| `AWS_SECRET_ACCESS_KEY` | `deploy.yml`, `destroy.yml` | Secret key paired with `AWS_ACCESS_KEY_ID` |
| `AWS_REGION` | `deploy.yml`, `destroy.yml` | Must match infra (e.g. `ap-southeast-1`) |
| `PULUMI_ACCESS_TOKEN` | `deploy.yml`, `destroy.yml` | [Pulumi Cloud](https://app.pulumi.com/) access token for `pulumi login` (non-interactive CI) |
| `SSH_PUBLIC_KEY` | `deploy.yml` → `pulumi config set sshPublicKey` | Public half of the SSH key pair; must match the key allowed on the EC2 instance (Pulumi `aws.ec2.KeyPair`) |
| `SSH_PRIVATE_KEY` | `deploy.yml` | Private key used by `scp`/`ssh` from the runner to `ubuntu@<instance_public_ip>` after `pulumi up` |
| `KAGGLE_USERNAME` | `deploy.yml` → remote `deploy_ec2_pipeline.sh` | Written to `~/.kaggle/kaggle.json` on EC2 |
| `KAGGLE_KEY` | `deploy.yml` → remote `deploy_ec2_pipeline.sh` | Kaggle API token |

## Optional secrets

| Secret | Used by | Purpose |
|--------|---------|---------|
| `PULUMI_CONFIG_PASSPHRASE` | `deploy.yml`, `destroy.yml` | Only if my Pulumi stack config is passphrase-encrypted; exported as env before `pulumi` commands |

If I do **not** use encrypted stack config, create an empty secret or omit it and remove the `env` entry from the workflows (or leave unset — empty env is usually fine).

---

## When to add `SSH_PRIVATE_KEY` vs `SSH_PUBLIC_KEY`

1. **Generate a dedicated key pair** for CI/infra (do not reuse my personal daily key if I can avoid it).

2. **Add `SSH_PUBLIC_KEY` first** (or at the same time as private):
   - Pulumi needs the **public** key when it runs `pulumi config set sshPublicKey …` so AWS can install `authorized_keys` on the new EC2 instance.
   - The **same** key pair must be used later for SSH from GitHub Actions.

3. **Add `SSH_PRIVATE_KEY` after** the instance exists **or** in the same release as the first deploy:
   - The private key is only used **after** `pulumi up` succeeds, in the “Upload and run pipeline script on EC2” step.
   - It must be the private key that matches `SSH_PUBLIC_KEY`.

**Order for a brand-new stack:** configure **both** secrets in GitHub **before** the first `deploy` workflow run, so Pulumi can create the instance with my public key and the runner can SSH with the private key.

---

## Producing keys on an Ubuntu VM

### Ed25519 (recommended)

```bash
ssh-keygen -t ed25519 -C "modelserve-ci-github" -f ~/.ssh/modelserve_github_ci -N ""
```

- **Public key** (for Pulumi / `SSH_PUBLIC_KEY` secret):

  ```bash
  cat ~/.ssh/modelserve_github_ci.pub
  ```

- **Private key** (for `SSH_PRIVATE_KEY` secret — entire file including header/footer):

  ```bash
  cat ~/.ssh/modelserve_github_ci
  ```

### RSA (if required by policy)

```bash
ssh-keygen -t rsa -b 4096 -C "modelserve-ci-github" -f ~/.ssh/modelserve_github_ci -N ""
cat ~/.ssh/modelserve_github_ci.pub   # → SSH_PUBLIC_KEY
cat ~/.ssh/modelserve_github_ci       # → SSH_PRIVATE_KEY
```

### Paste into GitHub

1. **SSH_PUBLIC_KEY**: paste the **single line** `.pub` content (starts with `ssh-ed25519` or `ssh-rsa`).
2. **SSH_PRIVATE_KEY**: paste the **full** private PEM (starts with `-----BEGIN … PRIVATE KEY-----`). Use a multiline secret; GitHub supports it.

**Security:** restrict repository access; rotate keys if leaked; prefer deploy keys or OIDC patterns for production hardening (out of scope for this capstone).

---

## Pulumi token

1. Sign in at [https://app.pulumi.com/](https://app.pulumi.com/).
2. **Settings → Access Tokens** → create token.
3. Add as `PULUMI_ACCESS_TOKEN`.

For fully local state without Pulumi Cloud, I would change the workflows to use `pulumi login --local` and a different state backend — not configured in the default workflows.

---

## Kaggle credentials

1. Kaggle account → **Account** → **Create New API Token** (downloads `kaggle.json`).
2. Map `username` → `KAGGLE_USERNAME`, `key` → `KAGGLE_KEY` as repository secrets.

---

## Quick validation

After secrets are set, run **Actions → Deploy (Pulumi + EC2)** by pushing to `main`, or use **Destroy (Pulumi)** manually to tear down the `dev` stack.

---

## End-to-end checklist (will training + `/predict` run automatically?)

**Yes, if all of the below are true** — the pipeline is designed to: Pulumi `up` → wait for Docker on EC2 → Kaggle download → `deploy_ec2.sh` (MLflow stack → train with `TRAIN_MAX_ROWS=50000` → Feast → full compose → `/health`).

1. **Branch:** Workflow triggers on **`push` to `main` only**. Merging or pushing directly to `main` runs deploy; other branches do not.
2. **GitHub repo visibility:** The EC2 script clones `https://github.com/<owner>/<repo>.git` with **no token**. **Private repos** will fail at `git clone` unless I add a PAT/deploy key (not in the default workflow).
3. **AWS IAM:** The access key used in secrets must be allowed to create/update everything in `infrastructure/__main__.py` (VPC, EC2, EIP, S3, ECR, IAM, …).
4. **Pulumi:** Same stack name **`dev`** as in the workflow; `PULUMI_ACCESS_TOKEN` must allow `pulumi login` non-interactively.
5. **SSH key pair:** `SSH_PUBLIC_KEY` (Pulumi `sshPublicKey`) and `SSH_PRIVATE_KEY` (Actions SSH) must be the **same** pair; otherwise Pulumi or SSH will fail.
6. **Kaggle:** `KAGGLE_USERNAME` / `KAGGLE_KEY` must be valid; download uses the official dataset slug `kartik2112/fraud-detection`.
7. **First boot timing:** The workflow **polls** `sudo docker info` over SSH (up to ~10 minutes) before `scp`/`ssh` deploy, so the Docker daemon from user-data is up before `docker compose` runs.

If any step fails, open the **Actions** log for the failed step (Pulumi, wait-for-Docker, `scp`, or the remote bash output).

---

## Private repository (optional)

To clone a **private** GitHub repo on EC2 I need credentials (e.g. fine-scoped PAT in a secret, `git clone https://x-access-token:TOKEN@github.com/...`, or a deploy key). The stock workflow only uses the public HTTPS URL.
