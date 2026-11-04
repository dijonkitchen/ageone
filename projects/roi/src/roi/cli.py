"""A thin demo entry point. Real CLIs/adapters layer on top of the core.

``uv run roi`` screens a small synthetic universe, then backtests a momentum
strategy through the paper broker — proving the whole pipeline runs offline.
``uv run roi research`` runs the research assistant on a sample shortlist (see
:mod:`roi.research`).
"""

from __future__ import annotations

import math
import sys
from collections.abc import Sequence
from datetime import datetime, timedelta

from . import research
from .adapters import InMemoryMarketData, ReplayMarketData
from .domain import Bar, Security
from .execution import PaperBroker
from .harness import backtest
from .screening import AboveSMA, PositiveMomentum, Screener, Snapshot, all_of
from .strategy import MomentumStrategy


def _series(symbol: str, *, base: float, drift: float, n: int = 80) -> list[Bar]:
    """A deterministic synthetic price series (sine wiggle around a drift)."""
    start = datetime(2024, 1, 1)
    bars = []
    for i in range(n):
        close = base * (1 + drift) ** i + math.sin(i / 3) * base * 0.01
        bars.append(
            Bar(start + timedelta(days=i), close, close, close, close, 1_000_000)
        )
    return bars


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["research"]:
        return research.main(args[1:])
    if args:
        print(
            "usage: roi [research [--role ROLE] [--prompt] [--check FILE]]",
            file=sys.stderr,
        )
        return 2
    demo()
    return 0


def demo() -> None:
    universe = {
        Security("RISE"): _series("RISE", base=100, drift=0.01),
        Security("FLAT"): _series("FLAT", base=50, drift=0.0),
        Security("FALL"): _series("FALL", base=80, drift=-0.01),
    }

    # 1) Screen on the full history.
    full = InMemoryMarketData(universe)
    screener = Screener(
        filters=[all_of(AboveSMA(50), PositiveMomentum(20))],
        score=lambda s: s.momentum(20),
    )
    snapshots = [Snapshot(sec, full.history(sec)) for sec in full.universe()]
    print("Screen (ranked by 20-bar momentum):")
    for result in screener.run(snapshots):
        print(f"  {result.security.symbol:5}  score={result.score:+.3f}")

    # 2) Backtest the momentum strategy through the paper broker.
    market = ReplayMarketData(universe)
    broker = PaperBroker(market, starting_cash=100_000.0)
    report = backtest(market, MomentumStrategy(), broker)
    print("\nBacktest:")
    print(f"  final equity : {report.final_equity:,.2f}")
    print(f"  total return : {report.total_return:+.2%}")
    print(f"  max drawdown : {report.max_drawdown:.2%}")
    print(f"  trades       : {report.n_trades}")
    print("\nResearch a sample shortlist with cited summaries: uv run roi research")


if __name__ == "__main__":
    sys.exit(main())
