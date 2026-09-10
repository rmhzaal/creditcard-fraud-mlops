
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import boto3
import pandas as pd
from evidently import Report
from evidently.presets import DataDriftPreset

PREDICTIONS_BUCKET = os.environ["PREDICTIONS_BUCKET"]
DATA_PATH = os.environ["DATA_PATH"]  # s3://.../reference/creditcard.csv
DRIFT_LOOKBACK_HOURS = float(os.environ.get("DRIFT_LOOKBACK_HOURS", "6"))
DRIFT_THRESHOLD = float(os.environ.get("DRIFT_THRESHOLD", "0.3"))
MIN_PREDICTIONS = 30  # below this there's not enough signal to judge anything

FEATURE_COLUMNS = ["Time"] + [f"V{i}" for i in range(1, 29)] + ["Amount"]


def load_reference() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    return df[FEATURE_COLUMNS]


def load_recent_predictions() -> pd.DataFrame:
    s3 = boto3.client("s3")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=DRIFT_LOOKBACK_HOURS)
    records = []

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=PREDICTIONS_BUCKET, Prefix="live-predictions/"):
        for obj in page.get("Contents", []):
            if obj["LastModified"] < cutoff:
                continue
            body = s3.get_object(Bucket=PREDICTIONS_BUCKET, Key=obj["Key"])["Body"].read()
            try:
                records.append(json.loads(body))
            except json.JSONDecodeError:
                continue  # skip anything malformed rather than fail the whole run

    if not records:
        return pd.DataFrame(columns=FEATURE_COLUMNS)

    df = pd.DataFrame(records)
    for c in FEATURE_COLUMNS:
        if c not in df.columns:
            df[c] = None
    return df[FEATURE_COLUMNS]


def compute_drift_share(reference: pd.DataFrame, current: pd.DataFrame) -> float:
    report = Report([DataDriftPreset()])
    result = report.run(reference, current)
    result_dict = result.dict()

    for metric in result_dict.get("metrics", []):
        metric_type = metric.get("config", {}).get("type", "")
        if "DriftedColumnsCount" in metric_type:
            value = metric.get("value", {})
            if isinstance(value, dict) and "share" in value:
                return float(value["share"])

    print("Could not find a DriftedColumnsCount metric in the report -- full result for debugging:")
    print(json.dumps(result_dict, indent=2, default=str)[:3000])
    raise RuntimeError("Evidently report did not contain a recognizable drift-share metric")


def trigger_retrain():
    print("Drift threshold breached -- triggering the Phase 4 retraining flow now.")
    subprocess.run([sys.executable, "-m", "src.flows"], check=True)


def main():
    reference = load_reference()
    current = load_recent_predictions()

    if len(current) < MIN_PREDICTIONS:
        print(f"Only {len(current)} live predictions in the last {DRIFT_LOOKBACK_HOURS}h "
              f"(need {MIN_PREDICTIONS}) -- skipping drift check for this run.")
        return

    drift_share = compute_drift_share(reference, current)
    print(f"Drift share: {drift_share:.2f} (threshold {DRIFT_THRESHOLD}) over {len(current)} live predictions")

    if drift_share > DRIFT_THRESHOLD:
        trigger_retrain()
    else:
        print("Drift share below threshold -- no retrain triggered.")


if __name__ == "__main__":
    main()
