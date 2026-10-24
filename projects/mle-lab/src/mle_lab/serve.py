"""Serve the champion over HTTP with MLflow's scoring server."""

import os
import sys
from pathlib import Path

from mle_lab.config import CHAMPION, MODEL_NAME

CHAMPION_URI = f"models:/{MODEL_NAME}@{CHAMPION}"


def http(port: int = 5001) -> None:
    """Replace this process with `mlflow models serve` on the champion, in the current environment."""
    bin_dir = Path(sys.executable).parent
    # MLflow starts the server with `uvicorn` from PATH, so put this environment's first.
    env = os.environ | {"PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
    mlflow_bin = str(bin_dir / "mlflow")
    args = [mlflow_bin, "models", "serve", "-m", CHAMPION_URI, "--env-manager", "local", "--port", str(port)]
    os.execve(mlflow_bin, args, env)
