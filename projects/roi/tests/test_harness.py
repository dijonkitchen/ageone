import pytest

from roi.adapters import ReplayMarketData
from roi.domain import Security
from roi.execution import PaperBroker
from roi.harness import EvalReport, backtest
from roi.strategy import MomentumStrategy

from .helpers import bars_from_closes


@pytest.mark.criteria("TRD-4")
def test_eval_report_drawdown_and_return() -> None:
    report = EvalReport.from_curve([100.0, 120.0, 90.0, 110.0], n_trades=3)
    assert report.total_return == pytest.approx(0.10)
    assert report.max_drawdown == pytest.approx(0.25)
    assert report.n_trades == 3


@pytest.mark.criteria("TRD-4")
def test_eval_report_no_drawdown_when_rising() -> None:
    report = EvalReport.from_curve([100.0, 101.0, 102.0], n_trades=0)
    assert report.max_drawdown == 0.0


def test_eval_report_retains_equity_curve() -> None:
    report = EvalReport.from_curve([100.0, 110.0, 105.0], n_trades=1)
    assert report.equity_curve == (100.0, 110.0, 105.0)


def rising_market() -> ReplayMarketData:
    closes = [10 + i for i in range(12)]  # strictly rising
    return ReplayMarketData({Security("UP"): bars_from_closes(closes)})


def run_once() -> EvalReport:
    # The broker prices off the same market the harness advances.
    market = rising_market()
    broker = PaperBroker(market, starting_cash=10_000.0)
    return backtest(market, MomentumStrategy(sma_window=3, momentum_window=2), broker)


@pytest.mark.criteria("TRD-3")
def test_backtest_is_deterministic() -> None:
    assert run_once() == run_once()


@pytest.mark.criteria("TRD-4")
def test_backtest_rising_market_profits_without_drawdown() -> None:
    market = rising_market()
    broker = PaperBroker(market, starting_cash=10_000.0)
    report = backtest(market, MomentumStrategy(sma_window=3, momentum_window=2), broker)
    assert report.n_trades > 0
    assert report.total_return > 0
    assert report.max_drawdown == 0.0
