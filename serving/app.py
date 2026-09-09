import os

import mlflow
import mlflow.pyfunc
import mlflow.sklearn
import pandas as pd
from fastapi import FastAPI
from mlflow.tracking import MlflowClient
from pydantic import BaseModel, ConfigDict

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow.creditcard-fraud-mlops.svc.cluster.local:5000")
REGISTERED_MODEL_NAME = "creditcard-fraud-xgb"
ALIAS = "champion"

app = FastAPI()
_model = None
_scaler = None


class Transaction(BaseModel):
    model_config = ConfigDict(extra="allow")  # accepts Time, Amount, V1..V28
    Time: float
    Amount: float


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


@app.post("/predict")
def predict(transaction: Transaction):
    row = pd.DataFrame([transaction.model_dump()])
    row[["Amount", "Time"]] = _scaler.transform(row[["Amount", "Time"]])

    fraud_probability = float(_model.predict(row)[0])
    return {
        "fraud_probability": fraud_probability,
        "is_fraud": fraud_probability >= 0.5,
    }
