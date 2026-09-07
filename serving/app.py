# Minimal for Phase 5 -- just enough for CI to build/scan/push/deploy
# end to end. Phase 6 adds the real /predict handler that loads the
# "champion" model from the MLflow registry; Phase 7 adds Prometheus
# metrics; Phase 8 adds prediction logging for the drift job to read.
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}
