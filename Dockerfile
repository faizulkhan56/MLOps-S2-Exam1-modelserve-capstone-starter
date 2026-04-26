# ModelServe — API image (Phases 1–2: single-stage; Phase 8 will add multi-stage hardening)
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# No build-essential yet: Phase 1–2 deps are pure wheels. Add gcc when mlflow/sklearn land.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

# Feast repo path mounted at runtime; include minimal copy for local builds
COPY feast_repo/ feast_repo/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
