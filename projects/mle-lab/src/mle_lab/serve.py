"""Serve the champion: batch scoring into DuckDB, and an HTTP server through MLflow's scoring server."""

import os
import sys
from pathlib import Path

import duckdb
import mlflow
import mlflow.pyfunc

from mle_lab import features
from mle_lab.config import CHAMPION, MODEL_NAME, Paths
from mle_lab.data import month_start

CHAMPION_URI = f"models:/{MODEL_NAME}@{CHAMPION}"


def score(paths: Paths, month: int) -> int:
    """Score every customer in `month` with the champion and store it in the `predictions` table."""
    version = str(mlflow.MlflowClient().get_model_version_by_alias(MODEL_NAME, CHAMPION).version)
    model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/{version}")
    snapshot = month_start(month).isoformat()
    with duckdb.connect(str(paths.warehouse)) as con:
        frame = features.load(con, [snapshot])
        out = frame[["customer_id", "snapshot_date"]].assign(
            model_version=version, churn_probability=model.predict(features.model_input(frame))[:, 1]
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS predictions (customer_id BIGINT, snapshot_date DATE, model_version VARCHAR, "
            "churn_probability DOUBLE, PRIMARY KEY (customer_id, snapshot_date))"
        )
        # Rescoring a month replaces its rows, so the table holds the latest model's view.
        con.execute("DELETE FROM predictions WHERE snapshot_date = $s::DATE", {"s": snapshot})
        con.register("scored", out)
        con.execute(
            "INSERT INTO predictions SELECT customer_id, snapshot_date, model_version, churn_probability FROM scored"
        )
    return len(out)


def http(port: int = 5001) -> None:
    """Replace this process with `mlflow models serve` on the champion, in the current environment."""
    bin_dir = Path(sys.executable).parent
    # MLflow starts the server with `uvicorn` from PATH, so put this environment's first.
    env = os.environ | {"PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
    mlflow_bin = str(bin_dir / "mlflow")
    args = [mlflow_bin, "models", "serve", "-m", CHAMPION_URI, "--env-manager", "local", "--port", str(port)]
    os.execve(mlflow_bin, args, env)
