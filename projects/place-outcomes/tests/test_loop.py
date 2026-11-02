from datetime import date

import duckdb
import mlflow

from place_outcomes import loop, months
from place_outcomes.config import EXPERIMENT, Paths

START = date(2012, 1, 1)
END = date(2016, 12, 1)


def test_replay_forecasts_monthly_retrains_through_the_gate_and_never_trains_on_the_future(lab: Paths) -> None:
    attempts, steps = loop.replay(lab, START, END)
    assert attempts[-1].promoted

    with duckdb.connect(str(lab.warehouse), read_only=True) as con:
        forecasts = con.execute("SELECT month, count(*) AS zips FROM forecasts GROUP BY month").df()
        total = con.execute(loop.SUMMARY_SQL).df().iloc[-1]
        monitoring = con.execute("SELECT * FROM monitoring").df()
    assert steps[-1].as_of == END
    assert len(forecasts) == len(steps) and set(forecasts["zips"]) == {40}
    assert monitoring["retrained"].sum() >= 3
    # Whether the model beats the baselines is judged on the full replay over every ZIP (see the README);
    # forty ZIPs are too few to train on, so here the summary only has to score every forecast, since
    # the fixture runs years past END.
    assert total["forecasts"] == forecasts["zips"].sum()

    runs = mlflow.search_runs(experiment_names=[EXPERIMENT], output_format="list")
    assert len(runs) == len(attempts) + monitoring["retrained"].sum()
    for run in runs:
        assert run.data.params["train_last_label"] <= run.data.params["eval_start"]
        assert run.data.params["eval_end"] < run.data.params["as_of"]


def test_step_forecasts_every_zip(lab: Paths) -> None:
    as_of = START
    while not loop.bootstrap(lab, as_of).promoted:  # Forty ZIPs are a thin training set; wait for a winner.
        as_of = months.add(as_of, loop.COOLDOWN_MONTHS)
    s = loop.step(lab, as_of)
    assert s.zips == 40 and s.median_forecast is not None and -0.5 < s.median_forecast < 0.5
    assert s.model_mae is None  # No forecast has its label yet.
