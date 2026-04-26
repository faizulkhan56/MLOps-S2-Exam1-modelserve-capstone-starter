# MLflow with Postgres (psycopg2) and S3 artifact support.
# The upstream ghcr.io/mlflow/mlflow image does not include psycopg2; without it
# `postgresql://...` backend store fails with: No module named 'psycopg2'
FROM ghcr.io/mlflow/mlflow:v2.16.0

# Base image is typically root; install drivers before any USER directive in the base
RUN pip install --no-cache-dir "psycopg2-binary>=2.9.9" "boto3>=1.28.0"
