import mlflow
import numpy as np
import pytest
from fastapi.testclient import TestClient
from mlflow.pyfunc import scoring_server

from mle_lab import model, serve
from mle_lab.config import CHALLENGER, CHAMPION, MODEL_NAME, Paths

AS_OF = "2022-06-01"


def test_qlike_is_zero_for_a_perfect_forecast_and_punishes_calling_a_storm_calm() -> None:
    realized = np.array([0.2, 0.3])
    assert model.qlike(realized, realized) == pytest.approx(0)
    assert model.qlike(realized, realized / 2) > model.qlike(realized, realized * 2)


@pytest.mark.parametrize(
    ("mine", "base", "theirs", "promoted"),
    [
        (0.3, 0.5, None, True),
        (0.6, 0.5, None, False),
        (0.3, 0.5, 0.4, True),
        (0.4, 0.5, 0.3, False),
        (0.45, 0.5, 0.6, True),  # The champion no longer beats the baseline.
    ],
)
def test_gate(mine: float, base: float, theirs: float | None, promoted: bool) -> None:
    assert model.decide(mine, base, theirs)[0] is promoted


def test_train_tracks_and_registers_a_challenger(lab: Paths) -> None:
    trained = model.train(lab, AS_OF)
    run = mlflow.get_run(trained.run_id)
    assert run.data.params["as_of"] == AS_OF
    # The newest label known on AS_OF is five trading days earlier.
    assert run.data.params["eval_end"] < AS_OF
    assert run.data.metrics["eval_qlike"] < run.data.metrics["baseline_qlike"]
    assert run.inputs is not None
    assert {d.dataset.name for d in run.inputs.dataset_inputs} == {"train", "eval"}
    assert model.version_for(CHALLENGER) == trained.version


def test_train_needs_enough_history(lab: Paths) -> None:
    with pytest.raises(SystemExit):
        model.train(lab, "2020-06-01")


def test_promote_records_the_gate_on_the_version(lab: Paths) -> None:
    model.train(lab, AS_OF)
    decision = model.promote(lab, AS_OF)
    assert decision.promoted
    assert model.version_for(CHAMPION) == decision.challenger
    tags = mlflow.MlflowClient().get_model_version(MODEL_NAME, decision.challenger).tags
    assert tags["promotion"] == "promoted"
    assert float(tags["gate_qlike"]) < float(tags["gate_baseline_qlike"])


def test_champion_serves_forecasts_over_http(lab: Paths) -> None:
    model.train(lab, AS_OF)
    model.promote(lab, AS_OF)
    # The same FastAPI app that `mlflow models serve` (and so `mle serve`) runs.
    client = TestClient(scoring_server.init(mlflow.pyfunc.load_model(serve.CHAMPION_URI)))
    calm = {"rv_1d": 0.05, "rv_5d": 0.08, "rv_21d": 0.1, "vix": 0.12}
    storm = {"rv_1d": 0.6, "rv_5d": 0.5, "rv_21d": 0.4, "vix": 0.45}
    response = client.post("/invocations", json={"dataframe_records": [calm, storm]})
    assert response.status_code == 200, response.text
    low, high = response.json()["predictions"]
    assert 0 < low < high
    assert client.post("/invocations", json={"dataframe_records": [{"vix": 0.2}]}).status_code == 400
