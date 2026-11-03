from datetime import date

import mlflow
import pandas as pd

from place_outcomes import model
from place_outcomes.config import CHALLENGER, CHAMPION, MODEL_NAME, Paths

AS_OF = date(2016, 1, 1)


def test_windows_purge_training_labels_before_the_eval_window() -> None:
    w = model.windows(AS_OF)
    assert w.eval_last == date(2015, 1, 1) and w.eval_first == date(2014, 2, 1)
    assert w.train_last == date(2013, 2, 1)  # Its label month is the first eval origin.


def test_train_logs_a_run_registers_a_challenger_and_never_trains_on_later_labels(lab: Paths) -> None:
    trained = model.train(lab, AS_OF)
    run = mlflow.get_run(trained.run_id)
    assert run.data.params["train_last_label"] <= run.data.params["eval_start"]
    assert run.data.params["eval_end"] == "2015-01-01"
    assert {"eval_mae", "nochange_mae", "momentum_mae"} <= set(run.data.metrics)
    assert model.version_for(CHALLENGER) == trained.version
    assert model.trained_as_of(trained.version) == AS_OF


def test_gate_decisions() -> None:
    assert model.decide(0.05, 0.06, 0.07, None)[0]
    assert not model.decide(0.065, 0.06, 0.07, None)[0]  # Must beat the better baseline.
    assert not model.decide(0.05, 0.08, 0.04, None)[0]
    assert model.decide(0.05, 0.06, 0.07, 0.05)[0]  # Ties with the champion ship.
    assert not model.decide(0.055, 0.06, 0.07, 0.05)[0]
    assert model.decide(0.055, 0.06, 0.07, 0.065)[0]  # A champion behind a baseline is replaced.


def test_promote_tags_the_decision_and_moves_the_alias(lab: Paths) -> None:
    trained = model.train(lab, AS_OF)
    decision = model.promote(lab, AS_OF)
    tags = mlflow.MlflowClient().get_model_version(MODEL_NAME, trained.version).tags
    assert tags["promotion"] == ("promoted" if decision.promoted else "rejected")
    assert tags["promotion_reason"] == decision.reason
    assert (model.version_for(CHAMPION) == trained.version) == decision.promoted


def test_baselines_are_flat_and_last_year() -> None:
    frame = pd.DataFrame({"r12": [0.1, -0.2]})
    b = model.baselines(frame)
    assert list(b["nochange"]) == [0.0, 0.0] and list(b["momentum"]) == [0.1, -0.2]
