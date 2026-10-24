from datetime import date

import duckdb
import mlflow

from mle_lab import loop
from mle_lab.config import EXPERIMENT, Paths

START = date(2025, 2, 1)


def test_replay_forecasts_daily_retrains_beats_naive_and_never_trains_on_the_future(lab: Paths) -> None:
    attempts, steps = loop.replay(lab, START)
    assert attempts[-1].promoted

    with duckdb.connect(str(lab.warehouse), read_only=True) as con:
        forecasts = con.execute("SELECT date, count(*) AS hours FROM forecasts GROUP BY date").df()
        total = con.execute(loop.SUMMARY_SQL).df().iloc[-1]
        monitoring = con.execute("SELECT * FROM monitoring").df()
    # Every morning through the one after the data's last day forecasts all of the next day.
    assert steps[0].as_of == START and steps[-1].as_of == date(2025, 5, 1)
    assert len(forecasts) == len(steps) and set(forecasts["hours"]) == {23, 24}  # 23 on the spring-forward day.
    assert monitoring["retrained"].sum() >= 2
    assert total["model_mape"] < total["naive_mape"]

    runs = mlflow.search_runs(experiment_names=[EXPERIMENT], output_format="list")
    assert len(runs) == len(attempts) + monitoring["retrained"].sum()
    for run in runs:
        assert run.data.params["eval_end"] < run.data.params["as_of"]


def test_step_forecasts_tomorrow(lab: Paths) -> None:
    loop.bootstrap(lab, START)
    s = loop.step(lab, START)
    assert s.target == date(2025, 2, 2)
    assert s.hours == 24 and s.peak is not None and 30_000 < s.peak < 90_000
    assert s.model_mape is None  # No forecasted day has its actuals yet.
