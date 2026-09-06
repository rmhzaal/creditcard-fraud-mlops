# Phase 4 of the guide. Wraps train.py in a Prefect flow so retraining is
# a repeatable, observable, retryable action rather than a one-off script
# run. We're not standing up a full Prefect server/deployment for a 2-day
# build -- GitHub Actions (Phase 5/8) triggers this by just running
# `python -m src.flows`, which gets you Prefect's run tracking and retries
# without an extra long-running service to operate.
from prefect import flow, task

from src.train import train as train_model


@task(retries=1, retry_delay_seconds=30)
def run_training():
    train_model()


@flow(name="fraud-model-retraining")
def retrain_flow():
    run_training()


if __name__ == "__main__":
    retrain_flow()
