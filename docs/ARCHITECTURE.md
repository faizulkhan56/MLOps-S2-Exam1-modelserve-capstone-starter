# ModelServe — Engineering Documentation

> **This document is a major graded deliverable (19 marks).** It must be complete,
> accurate, and detailed enough that another engineer could understand and
> reproduce the system without looking at the code.

---

## 1. System Overview

<!-- TODO: Write 2-3 paragraphs describing:
     - What the system does and who it serves
     - The key design philosophy (e.g., simplicity vs availability, cost vs performance)
     - A high-level summary of the tech stack and deployment model -->

---

## 2. Architecture Diagram(s)

<!-- TODO: Include at least one diagram showing:
     - Every component (FastAPI, MLflow, Feast, Redis, Postgres, Prometheus, Grafana)
     - Where each component runs (Poridhi VM, AWS EC2, or both)
     - How components communicate (ports, protocols, network boundaries)
     - External dependencies (S3, ECR, GitHub Actions)

     Use any tool: Excalidraw, draw.io, Mermaid, ASCII art, hand-drawn.
     Save the image in docs/diagrams/ and reference it here.

     If you have separate local-development and production topologies,
     include a diagram for EACH. -->

---

## 3. Architecture Decision Records (ADRs)

<!-- TODO: Write at least FIVE ADRs covering the topics below.
     Each ADR must follow this format:

     ### ADR-N: [Title]
     **Context:** What situation or problem prompted this decision?
     **Decision:** What did you decide?
     **Rationale:** Why this choice over the alternatives?
     **Trade-offs:** What did you give up? What risks does this introduce?
-->

### ADR-1: Deployment Topology
<!-- Why did you choose to deploy where you did? Single node? Hybrid? Why? -->

### ADR-2: CI/CD Strategy
<!-- Destroy-and-recreate vs incremental update? Why? -->

### ADR-3: Data Architecture
<!-- Why Postgres for MLflow? Why Redis for Feast? Why S3 for artifacts? -->

### ADR-4: Containerization
<!-- Base image choice? Multi-stage strategy? Image size trade-offs? -->

### ADR-5: Monitoring Design
<!-- Why these alert thresholds? What is the dashboard optimized to show? -->

---

## 4. CI/CD Pipeline Documentation

<!-- TODO: Describe your GitHub Actions workflow:
     - What each job does and what triggers it
     - What secrets are required
     - How failures are handled
     - Expected end-to-end deploy time -->

---

## 5. Runbook

<!-- TODO: Write concise operational procedures for: -->

### 5.1 Bootstrapping from a Fresh Clone
<!-- Step-by-step including secrets setup, dataset download, first deploy -->

### 5.2 Deploying a New Model Version
<!-- How to retrain and deploy without restarting everything -->

### 5.3 Common Failure Recovery
<!-- Diagnose and fix: service crash, S3 permission loss, Pulumi state corruption, Redis data loss -->

### 5.4 Teardown
<!-- How to cleanly destroy everything (Pulumi, Docker, AWS resources) -->

---

## 6. Known Limitations

<!-- TODO: Be honest about:
     - What the system does NOT handle well
     - What you would improve with more time
     - What would need to change for a real production deployment
     - Any shortcuts you took and why -->

