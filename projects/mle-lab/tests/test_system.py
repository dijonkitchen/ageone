"""Definition of done items 3 and 4: the system on a small generated dataset."""

import json

import duckdb
import mlflow
import mlflow.pyfunc
import pytest
from fastapi.testclient import TestClient
from mlflow.pyfunc import scoring_server

from mle_lab import loop, monitor, registry, serve, train
from mle_lab.config import CHALLENGER, CHAMPION, MODEL_NAME, TRAINING_EXPERIMENT, Months, Paths
from mle_lab.evaluate import Evaluation

MONTHS = Months()


def bootstrap(lab: Paths) -> train.Trained:
    trained = train.train(lab, "logreg", MONTHS.train, MONTHS.validation)
    assert registry.promote(lab, MONTHS.validation).promoted
    return trained


def test_train_tracks_the_run_and_registers_a_challenger(lab: Paths) -> None:
    trained = train.train(lab, "logreg", MONTHS.train, MONTHS.validation)

    run = mlflow.get_run(trained.run_id)
    assert run.data.params["model"] == "logreg"
    assert train.trained_months(trained.version) == list(MONTHS.train)
    assert trained.metrics["eval_roc_auc"] > 0.7
    assert run.inputs is not None
    assert {d.dataset.name for d in run.inputs.dataset_inputs} == {"train", "eval"}
    assert mlflow.get_experiment(run.info.experiment_id).name == TRAINING_EXPERIMENT
    challenger = mlflow.MlflowClient().get_model_version_by_alias(MODEL_NAME, CHALLENGER)
    assert str(challenger.version) == trained.version


def test_train_refuses_to_evaluate_on_months_it_trained_on(lab: Paths) -> None:
    with pytest.raises(ValueError):
        train.train(lab, "logreg", [1, 2, 3], 3)


def evaluation(auc: float, failures: list[str] | None = None) -> Evaluation:
    return Evaluation(1, "1", 100, {"roc_auc": auc}, {}, failures or [])


@pytest.mark.parametrize(
    ("challenger", "champion", "promoted"),
    [
        (evaluation(0.8), None, True),
        (evaluation(0.9, ["calibration gap"]), None, False),
        (evaluation(0.8), evaluation(0.85), False),
        (evaluation(0.8), evaluation(0.8), True),
        (evaluation(0.7), evaluation(0.9, ["calibration gap"]), True),
    ],
)
def test_promotion_follows_the_gates(challenger: Evaluation, champion: Evaluation | None, promoted: bool) -> None:
    assert registry.decide(challenger, champion, min_gain=0.0)[0] is promoted


def test_promote_records_evals_and_keeps_the_better_champion(lab: Paths) -> None:
    first = bootstrap(lab)
    train.train(lab, "hgb", MONTHS.train, MONTHS.validation)
    # An impossible gain keeps the first champion whatever the second scored.
    decision = registry.promote(lab, MONTHS.validation, min_gain=1.0)

    assert not decision.promoted
    assert registry.version_for(CHAMPION) == first.version
    tags = mlflow.MlflowClient().get_model_version(MODEL_NAME, decision.challenger.model_version).tags
    assert tags["promotion"] == "rejected"
    with duckdb.connect(str(lab.warehouse), read_only=True) as con:
        roles = con.execute("SELECT role, count(*) FROM evaluations GROUP BY role ORDER BY role").fetchall()
    assert roles == [("challenger", 2), ("champion", 1)]


def test_promote_needs_a_challenger(lab: Paths) -> None:
    with pytest.raises(SystemExit):
        registry.promote(lab, MONTHS.validation)


def test_champion_serves_probabilities_over_http(lab: Paths) -> None:
    bootstrap(lab)
    # The same FastAPI app that `mlflow models serve` (and so `mle serve`) runs.
    client = TestClient(scoring_server.init(mlflow.pyfunc.load_model(serve.CHAMPION_URI)))
    assert client.get("/ping").status_code == 200
    record = {
        "plan": "basic",
        "region": "eu",
        "tenure_days": 30,
        "logins_30d": 0,
        "tickets_30d": 3,
        "payment_failures_30d": 1,
        "days_since_login": 40,
    }
    response = client.post("/invocations", json={"dataframe_records": [record]})
    assert response.status_code == 200, response.text
    [[stay, churn]] = response.json()["predictions"]
    assert stay + churn == pytest.approx(1)
    assert churn > 0.5
    # The model's signature rejects inputs missing features.
    assert client.post("/invocations", json={"dataframe_records": [{"plan": "basic"}]}).status_code == 400


def test_monitoring_is_quiet_before_the_release_and_alerts_after(lab: Paths) -> None:
    bootstrap(lab)
    before, after = MONTHS.drift_from, MONTHS.drift_from + 1
    for month in (before, after):
        assert serve.score(lab, month) > 0

    clean, drifted = monitor.monitor(lab, before), monitor.monitor(lab, after)
    assert clean.alerts == []
    assert any("logins_30d" in a for a in drifted.alerts)
    assert any("tickets_30d" in a for a in drifted.alerts)

    report = json.loads((lab.reports / "monitor-2026-11-01.json").read_text())
    assert report["alerts"] == drifted.alerts
    runs = mlflow.search_runs(experiment_names=["churn-monitoring"], output_format="list")
    assert {r.data.tags["alert"] for r in runs} == {"True", "False"}


def test_feedback_loop_retrains_on_new_labels_and_recovers(lab: Paths) -> None:
    """After the release, the loop retrains and promotes a model that saw post-release data."""
    first = bootstrap(lab)
    turns = [loop.turn(lab, month, kinds=("logreg",)) for month in MONTHS.production]

    assert not turns[0].retrained, "no alert before the release"
    assert any(t.retrained for t in turns)
    promotions = [d for t in turns for d in t.decisions if d.promoted]
    assert promotions, "a challenger earned promotion"
    champion = registry.version_for(CHAMPION)
    assert champion != first.version
    assert champion is not None and max(train.trained_months(champion)) > MONTHS.drift_from
    # Training never sees the month it is judged on.
    for t in turns:
        for d in t.decisions:
            assert max(train.trained_months(d.challenger.model_version)) < t.month
    # The last month is served by the new champion and passes the gates.
    assert turns[-1].report.model_version != first.version
    assert turns[-1].report.served.passed
