import os
import time

import mlflow
import mlflow.pyfunc
import mlflow.sklearn
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import Response
from mlflow.tracking import MlflowClient
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, ConfigDict

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow.creditcard-fraud-mlops.svc.cluster.local:5000")
REGISTERED_MODEL_NAME = "creditcard-fraud-xgb"
ALIAS = "champion"

FEATURE_COLUMNS = ["Time"] + [f"V{i}" for i in range(1, 29)] + ["Amount"]

app = FastAPI()
_model = None
_scaler = None

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
    response = await call_next(request)
    duration = time.time() - start
    REQUEST_LATENCY.labels(request.method, request.url.path).observe(duration)
    REQUEST_COUNT.labels(request.method, request.url.path, response.status_code).inc()
    return response


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


@app.post("/predict")
def predict(transaction: Transaction):
    row = pd.DataFrame([transaction.model_dump()])
    row[["Amount", "Time"]] = _scaler.transform(row[["Amount", "Time"]])
    row = row[FEATURE_COLUMNS]

    fraud_probability = float(_model.predict(row)[0])
    PREDICTION_SCORE.observe(fraud_probability)

    return {
        "fraud_probability": fraud_probability,
        "is_fraud": fraud_probability >= 0.5,
    }
