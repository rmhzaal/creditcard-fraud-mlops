import json
import os
import time
import uuid

import boto3
import mlflow
import mlflow.pyfunc
import mlflow.sklearn
import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import Response
from mlflow.tracking import MlflowClient
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, ConfigDict

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow.creditcard-fraud-mlops.svc.cluster.local:5000")
REGISTERED_MODEL_NAME = "creditcard-fraud-xgb"
ALIAS = "champion"
PREDICTIONS_BUCKET = os.environ.get("PREDICTIONS_BUCKET")  # set from terraform output mlflow_artifacts_bucket
SIMULATE_FAILURE = os.environ.get("SIMULATE_FAILURE", "false").lower() == "true"

FEATURE_COLUMNS = ["Time"] + [f"V{i}" for i in range(1, 29)] + ["Amount"]

app = FastAPI()
_model = None
_scaler = None
_s3 = boto3.client("s3") if PREDICTIONS_BUCKET else None

REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "Request latency in seconds", ["method", "path"])
PREDICTION_SCORE = Histogram(
    "fraud_prediction_score",
    "Distribution of predicted fraud probabilities",
    buckets=[0.0, 0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0],
)


class Transaction(BaseModel):
    model_config = ConfigDict(extra="allow")  # accepts Time, Amount, V1..V28
    Time: float
    Amount: float


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    start = time.time()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration = time.time() - start
        REQUEST_LATENCY.labels(request.method, request.url.path).observe(duration)
        REQUEST_COUNT.labels(request.method, request.url.path, status_code).inc()


@app.on_event("startup")
def load_champion():
    global _model, _scaler
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient()

    mv = client.get_model_version_by_alias(REGISTERED_MODEL_NAME, ALIAS)
    _model = mlflow.pyfunc.load_model(f"models:/{REGISTERED_MODEL_NAME}@{ALIAS}")
    _scaler = mlflow.sklearn.load_model(f"runs:/{mv.run_id}/scaler")
    print(f"Loaded champion version {mv.version} (run {mv.run_id})")


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": _model is not None}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _log_prediction_to_s3(raw_features: dict, fraud_probability: float):
    if _s3 is None:
        return
    record = {**raw_features, "fraud_probability": fraud_probability}
    key = f"live-predictions/{time.strftime('%Y-%m-%d')}/{uuid.uuid4()}.json"
    try:
        _s3.put_object(Bucket=PREDICTIONS_BUCKET, Key=key, Body=json.dumps(record))
    except Exception as e:
        print(f"Failed to log prediction to S3: {e}")  # never let logging break a prediction


@app.post("/predict")
def predict(transaction: Transaction, background_tasks: BackgroundTasks):
    if SIMULATE_FAILURE:
        # Deliberate chaos-test hook for the Phase 8 rollback test. Never
        # set true in a real deploy -- only for the one-off test.
        raise HTTPException(status_code=500, detail="Simulated failure for rollback test")

    raw_features = transaction.model_dump()
    row = pd.DataFrame([raw_features])
    row[["Amount", "Time"]] = _scaler.transform(row[["Amount", "Time"]])
    row = row[FEATURE_COLUMNS]

    fraud_probability = float(_model.predict(row)[0])
    PREDICTION_SCORE.observe(fraud_probability)

    background_tasks.add_task(_log_prediction_to_s3, raw_features, fraud_probability)

    return {
        "fraud_probability": fraud_probability,
        "is_fraud": fraud_probability >= 0.5,
    }
