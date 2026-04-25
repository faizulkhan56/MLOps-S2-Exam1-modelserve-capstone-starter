# ============================================================================
# ModelServe — Model Training Script
# ============================================================================
# TODO: Implement model training and MLflow registration.
#
# Dataset: https://www.kaggle.com/datasets/kartik2112/fraud-detection
#   - Use fraudTrain.csv (~1.3M rows, 22 features)
#   - Target column: is_fraud
#   - Entity key: cc_num
#   - Use class_weight='balanced' to handle class imbalance
#
# This script should:
#   1. Load fraudTrain.csv with pandas
#   2. Select and engineer features (15-20 features is enough)
#   3. Split into train/test sets (stratified on is_fraud)
#   4. Train a sklearn-compatible model (RandomForest, XGBoost, LightGBM)
#   5. Log to MLflow:
#      - Parameters: model type, hyperparameters, feature list
#      - Metrics: accuracy, precision, recall, f1, roc_auc
#      - The model artifact itself
#   6. Register the model in MLflow Model Registry
#   7. Transition the model version to "Production" stage
#   8. Export features.parquet (feature columns + cc_num + event_timestamp)
#      for Feast ingestion
#   9. Export sample_request.json with a valid entity_id for testing
#
# Prerequisites:
#   - MLflow and Postgres must be running (docker compose up postgres mlflow)
#   - fraudTrain.csv must be downloaded from Kaggle
#
# Usage:
#   python training/train.py
#
# IMPORTANT: This script must be reproducible — running it again should
# register a new model version with comparable metrics.
# Do NOT spend more than one session on model quality.
# A baseline AUC of 0.85+ is sufficient.
# ============================================================================
