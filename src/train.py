# Phase 4 of the guide. Trains an XGBoost fraud classifier, logs everything
# to MLflow, and only promotes the new version if it beats the current
# "champion" -- this gate is what makes it safe to let Phase 8 trigger this
# script automatically on drift, without a human reviewing every run.
#
# Note: MLflow's old Staging/Production "stages" are deprecated. We use
# a "champion" alias instead -- see Section 2.5 of the PDF guide.
import os

import mlflow
import mlflow.xgboost
import pandas as pd
from mlflow.tracking import MlflowClient
from sklearn.metrics import average_precision_score, precision_recall_curve
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from src.features import engineer_features

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
EXPERIMENT_NAME = "creditcard-fraud-detection"
REGISTERED_MODEL_NAME = "creditcard-fraud-xgb"
ALIAS = "champion"


def recall_at_precision(y_true, y_scores, target_precision: float = 0.9) -> float:
    """How much fraud you'd catch while keeping false-positive rate low
    enough that precision stays >= target_precision. More meaningful than
    accuracy on a dataset where ~99.8% of transactions are legitimate."""
    precision, recall, _ = precision_recall_curve(y_true, y_scores)
    eligible = recall[precision >= target_precision]
    return float(eligible.max()) if len(eligible) else 0.0


def load_data(path: str = "data/raw/creditcard.csv"):
    df = pd.read_csv(path)
    df = engineer_features(df)
    X = df.drop(columns=["Class"])
    y = df["Class"]
    return train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)


def get_current_champion_pr_auc(client: MlflowClient) -> float:
    try:
        mv = client.get_model_version_by_alias(REGISTERED_MODEL_NAME, ALIAS)
        run = client.get_run(mv.run_id)
        return run.data.metrics.get("pr_auc", 0.0)
    except Exception:
        return 0.0  # no champion registered yet -- first run always promotes


def train() -> None:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    X_train, X_test, y_train, y_test = load_data()

    with mlflow.start_run() as run:
        model = XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            scale_pos_weight=(y_train == 0).sum() / (y_train == 1).sum(),
            eval_metric="aucpr",
        )
        model.fit(X_train, y_train)

        y_scores = model.predict_proba(X_test)[:, 1]
        pr_auc = average_precision_score(y_test, y_scores)
        recall_p90 = recall_at_precision(y_test, y_scores, target_precision=0.9)

        mlflow.log_params(model.get_params())
        mlflow.log_metric("pr_auc", pr_auc)
        mlflow.log_metric("recall_at_p90", recall_p90)
        mlflow.xgboost.log_model(model, artifact_path="model")

        print(f"Run {run.info.run_id}: PR-AUC={pr_auc:.4f}  recall@P90={recall_p90:.4f}")

        client = MlflowClient()
        champion_pr_auc = get_current_champion_pr_auc(client)
        print(f"Current champion PR-AUC: {champion_pr_auc:.4f}")

        if pr_auc > champion_pr_auc:
            model_uri = f"runs:/{run.info.run_id}/model"
            mv = mlflow.register_model(model_uri, REGISTERED_MODEL_NAME)
            client.set_registered_model_alias(REGISTERED_MODEL_NAME, ALIAS, mv.version)
            print(f"Promoted version {mv.version} to '{ALIAS}' ({pr_auc:.4f} beat {champion_pr_auc:.4f})")
        else:
            print(f"Not promoted -- {pr_auc:.4f} did not beat current champion {champion_pr_auc:.4f}")


if __name__ == "__main__":
    train()
