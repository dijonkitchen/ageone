"""Deterministic, offline backtest harness (Spec 0003).

This is the evaluation harness: given the same fixtures, strategy, and broker
config it always produces the same :class:`EvalReport`. The report is the
outcome metric strategies are tuned against.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from .domain import Action, Bar, Order, OrderSide, Security, Signal
from .execution import BrokerError, PaperBroker
from .screening import Snapshot
from .strategy import Strategy


class ReplayMarketDataLike(Protocol):
    """Port the harness drives. ``ReplayMarketData`` satisfies it structurally."""

    def advance(self) -> bool: ...
    def universe(self) -> Sequence[Security]: ...
    def history(
        self, security: Security, *, limit: int | None = None
    ) -> Sequence[Bar]: ...
    def latest(self, security: Security) -> Bar: ...


#: Translate a signal into an order given the current broker state, or ``None``
#: to skip. Injectable so position sizing is a policy decision, not hard-coded.
Sizer = Callable[[Signal, PaperBroker], "Order | None"]


def fixed_fraction_sizer(fraction: float = 0.1) -> Sizer:
    """Spend up to ``fraction`` of equity per buy; sell the whole position."""

    def size(signal: Signal, broker: PaperBroker) -> Order | None:
        if signal.action is Action.BUY:
            price = broker.last_price(signal.security)
            qty = int((broker.equity() * fraction) // price)
            return Order(signal.security, OrderSide.BUY, qty) if qty > 0 else None
        if signal.action is Action.SELL:
            held = broker.position(signal.security)
            if held is not None:
                return Order(signal.security, OrderSide.SELL, held.quantity)
        return None

    return size


@dataclass(frozen=True, slots=True)
class EvalReport:
    final_equity: float
    total_return: float
    max_drawdown: float
    n_trades: int
    equity_curve: tuple[float, ...] = ()

    @classmethod
    def from_curve(cls, equity_curve: Sequence[float], n_trades: int) -> EvalReport:
        if not equity_curve:
            raise ValueError("empty equity curve")
        start, final = equity_curve[0], equity_curve[-1]
        peak = equity_curve[0]
        max_dd = 0.0
        for value in equity_curve:
            peak = max(peak, value)
            if peak > 0:
                max_dd = max(max_dd, (peak - value) / peak)
        total_return = (final / start - 1.0) if start else 0.0
        return cls(final, total_return, max_dd, n_trades, tuple(equity_curve))


def backtest(
    market: ReplayMarketDataLike,
    strategy: Strategy,
    broker: PaperBroker,
    *,
    sizer: Sizer | None = None,
) -> EvalReport:
    """Walk the timeline bar by bar, trade the strategy, and report the outcome."""
    size = sizer or fixed_fraction_sizer()
    equity_curve: list[float] = []
    n_trades = 0
    while market.advance():
        snapshots = [
            Snapshot(security, market.history(security))
            for security in market.universe()
        ]
        for signal in strategy(snapshots):
            order = size(signal, broker)
            if order is None:
                continue
            try:
                broker.submit(order)
                n_trades += 1
            except BrokerError:
                # Rejected by a risk limit; skip and keep going.
                continue
        equity_curve.append(broker.equity())
    return EvalReport.from_curve(equity_curve, n_trades)
