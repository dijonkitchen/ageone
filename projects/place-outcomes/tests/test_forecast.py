from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from place_outcomes import forecast
from place_outcomes.config import HORIZON, Paths


def test_gate_requires_beating_both_baselines_and_the_champion() -> None:
    assert forecast.gate(0.03, 0.05, 0.04, None).promote
    assert forecast.gate(0.03, 0.05, 0.04, 0.03).promote  # at least as good as the champion
    assert not forecast.gate(0.05, 0.05, 0.06, None).promote  # ties no-change
    assert not forecast.gate(0.03, 0.05, 0.02, None).promote  # momentum wins
    assert not forecast.gate(0.03, 0.05, 0.04, 0.025).promote  # champion wins


def test_features_use_only_months_up_to_the_as_of_month(con: duckdb.DuckDBPyConnection) -> None:
    panel = forecast.load_panel(con)
    t = 100
    before = forecast.features_at(panel, t)
    altered = panel.log_value.copy()
    altered.iloc[t + 1 :] = 99.0
    after = forecast.features_at(forecast.Panel(altered, panel.statics), t)
    pd.testing.assert_frame_equal(before, after)


def test_training_labels_have_matured_by_the_as_of_month(con: duckdb.DuckDBPyConnection) -> None:
    panel = forecast.load_panel(con)
    as_of = 120
    _x, y = forecast.training_rows(panel, as_of - HORIZON - forecast.GATE_MONTHS)
    # Training and gate rows are disjoint in time, and every label's end month is at or before the as-of month.
    gx, _ = forecast.gate_data(panel, as_of)
    assert y.notna().all()
    altered = panel.log_value.copy()
    altered.iloc[as_of + 1 :] = 99.0  # months published after the as-of month
    _x2, y2 = forecast.training_rows(forecast.Panel(altered, panel.statics), as_of - HORIZON - forecast.GATE_MONTHS)
    gx2, gy2 = forecast.gate_data(forecast.Panel(altered, panel.statics), as_of)
    pd.testing.assert_series_equal(y, y2)
    pd.testing.assert_frame_equal(gx, gx2)
    assert np.isfinite(gy2).all()


def test_gate_window_is_the_newest_twelve_months_of_matured_labels(con: duckdb.DuckDBPyConnection) -> None:
    panel = forecast.load_panel(con)
    as_of = 120
    gx, _ = forecast.gate_data(panel, as_of)
    # One row per ZIP per starting month, for 12 months; the newest one's label arrives in the as-of month.
    zips = gx.index.nunique()
    assert zips * (forecast.GATE_MONTHS - 1) < len(gx) <= zips * forecast.GATE_MONTHS


def test_step_and_replay_log_runs_and_promote(con: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    panel = forecast.load_panel(con)
    paths = Paths(tmp_path)
    table = forecast.replay(con, panel, paths, "2019-01", "2020-06")
    steps = con.execute("SELECT count(*), sum(promoted::INT) FROM steps").fetchall()[0]
    assert steps[0] == 18
    assert steps[1] >= 1
    assert {"model", "momentum", "no_change"} == set(table.columns)
    assert "all" in table.index
    client = forecast.setup(paths)
    assert forecast.champion_model(client) is not None
    out = forecast.forecast_at(panel, len(panel.months) - 1, client)
    assert out is not None
    assert out["truth"].isna().all()  # the future has not happened yet


def test_champion_absent_before_first_promotion(tmp_path: Path) -> None:
    client = forecast.setup(Paths(tmp_path))
    with pytest.raises(Exception):  # noqa: B017 - nothing registered yet
        client.get_model_version_by_alias(forecast.MODEL_NAME, "champion")
    assert forecast.champion_model(client) is None
