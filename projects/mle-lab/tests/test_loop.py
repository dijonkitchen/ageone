import duckdb
import mlflow

from mle_lab import features, loop
from mle_lab.config import EXPERIMENT, HORIZON, Paths

START = "2022-01-03"


def test_replay_forecasts_daily_retrains_and_beats_the_baseline(lab: Paths) -> None:
    steps = loop.replay(lab, START)

    with duckdb.connect(str(lab.warehouse), read_only=True) as con:
        days = con.execute("SELECT count(*) FROM features WHERE date > $d::DATE", {"d": START}).fetchone()
        summary = con.execute(loop.SUMMARY_SQL).df()
        monitoring = con.execute("SELECT * FROM monitoring").df()
    assert days is not None and len(steps) == days[0]
    assert monitoring["retrained"].sum() >= 2
    assert summary["model_qlike"].mean() < summary["baseline_qlike"].mean()


def test_replay_never_trains_on_labels_from_the_future(lab: Paths) -> None:
    loop.replay(lab, START)
    runs = mlflow.search_runs(experiment_names=[EXPERIMENT], output_format="list")
    assert len(runs) >= 3
    with duckdb.connect(str(lab.warehouse), read_only=True) as con:
        for run in runs:
            as_of = features.day_of(con, run.data.params["as_of"])
            eval_end = features.day_of(con, run.data.params["eval_end"])
            assert eval_end <= as_of - HORIZON


def test_step_forecasts_one_day(lab: Paths) -> None:
    loop.bootstrap(lab, START)
    with duckdb.connect(str(lab.warehouse), read_only=True) as con:
        day = features.day_of(con, START) + 1
    s = loop.step(lab, day)
    assert 0 < s.forecast < 2
    assert s.model_qlike is None  # No forecast has matured yet.
