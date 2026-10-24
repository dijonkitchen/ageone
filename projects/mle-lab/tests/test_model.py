from datetime import date

import duckdb
import mlflow
import numpy as np
import pytest
from fastapi.testclient import TestClient
from mlflow.pyfunc import scoring_server

from mle_lab import features, model, serve
from mle_lab.config import CHALLENGER, CHAMPION, FEATURES, MODEL_NAME, Paths

AS_OF = date(2025, 3, 1)


def test_mape_is_the_mean_share_off() -> None:
    actual = np.array([100.0, 200.0])
    assert model.mape(actual, actual) == 0
    assert model.mape(actual, np.array([110.0, 180.0])) == pytest.approx(0.1)


@pytest.mark.parametrize(
    ("mine", "naive", "theirs", "promoted"),
    [
        (0.03, 0.05, None, True),
        (0.06, 0.05, None, False),
        (0.03, 0.05, 0.04, True),
        (0.04, 0.05, 0.03, False),
        (0.045, 0.05, 0.06, True),  # The champion no longer beats naive.
    ],
)
def test_gate(mine: float, naive: float, theirs: float | None, promoted: bool) -> None:
    assert model.decide(mine, naive, theirs)[0] is promoted


def test_train_tracks_and_registers_a_challenger(lab: Paths) -> None:
    trained = model.train(lab, AS_OF)
    run = mlflow.get_run(trained.run_id)
    params, metrics = run.data.params, run.data.metrics
    assert params["as_of"] == "2025-03-01"
    # Labels known on the morning of AS_OF run through the day before.
    assert (params["eval_start"], params["eval_end"]) == ("2025-02-01", "2025-02-28")
    assert params["train_end"] == "2025-01-31"
    assert metrics["eval_mape"] < metrics["naive_mape"]
    assert metrics["operator_mape"] < metrics["eval_mape"]  # The operator has weather forecasts; we don't yet.
    assert run.inputs is not None
    assert {d.dataset.name for d in run.inputs.dataset_inputs} == {"train", "eval"}
    assert model.version_for(CHALLENGER) == trained.version


def test_train_needs_enough_history(lab: Paths) -> None:
    with pytest.raises(SystemExit):
        model.train(lab, date(2024, 9, 1))


def test_promote_records_the_gate_on_the_version(lab: Paths) -> None:
    model.train(lab, AS_OF)
    decision = model.promote(lab, AS_OF)
    assert decision.promoted, decision.reason
    assert model.version_for(CHAMPION) == decision.challenger
    tags = mlflow.MlflowClient().get_model_version(MODEL_NAME, decision.challenger).tags
    assert tags["promotion"] == "promoted"
    assert float(tags["gate_mape"]) < float(tags["gate_naive_mape"])


def test_champion_serves_forecasts_over_http(lab: Paths) -> None:
    model.train(lab, AS_OF)
    model.promote(lab, AS_OF)
    with duckdb.connect(str(lab.warehouse), read_only=True) as con:
        hours = features.day(con, date(2025, 3, 2))
    # The same FastAPI app that `mlflow models serve` (and so `mle serve`) runs.
    client = TestClient(scoring_server.init(mlflow.pyfunc.load_model(serve.CHAMPION_URI)))
    records = features.model_input(hours).to_dict("records")
    response = client.post("/invocations", json={"dataframe_records": records})
    assert response.status_code == 200, response.text
    forecast = np.array(response.json()["predictions"])
    assert model.mape(hours["demand"].to_numpy(), forecast) < 0.1
    missing = {k: v for k, v in records[0].items() if k != FEATURES[-1]}
    assert client.post("/invocations", json={"dataframe_records": [missing]}).status_code == 400
