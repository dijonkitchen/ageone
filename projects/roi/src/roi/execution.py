"""Simulated execution (Spec 0003).

``PaperBroker`` is the only broker in the toolkit. It never reaches a real
account; a live adapter is deliberate future work and must reuse these same
risk checks.
"""

from __future__ import annotations

from collections.abc import Sequence

from .domain import Fill, Order, OrderSide, Position, Security
from .ports import MarketDataProvider


class BrokerError(Exception):
    """Base class for order rejections."""


class InsufficientFunds(BrokerError):
    pass


class InsufficientHolding(BrokerError):
    pass


class RiskLimitExceeded(BrokerError):
    pass


class PaperBroker:
    """A cash account that fills orders at the latest close of a price source."""

    def __init__(
        self,
        price_source: MarketDataProvider,
        *,
        starting_cash: float = 100_000.0,
        max_position_value: float | None = None,
    ) -> None:
        self._prices = price_source
        self._cash = starting_cash
        self._max_position_value = max_position_value
        self._positions: dict[str, Position] = {}
        self._fills: list[Fill] = []

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def fills(self) -> Sequence[Fill]:
        return tuple(self._fills)

    def positions(self) -> Sequence[Position]:
        return tuple(self._positions.values())

    def position(self, security: Security) -> Position | None:
        return self._positions.get(security.symbol)

    def last_price(self, security: Security) -> float:
        return self._prices.latest(security).close

    def market_value(self) -> float:
        total = 0.0
        for pos in self._positions.values():
            total += pos.quantity * self._prices.latest(pos.security).close
        return total

    def equity(self) -> float:
        """Cash plus the market value of open positions."""
        return self._cash + self.market_value()

    def submit(self, order: Order) -> Fill:
        bar = self._prices.latest(order.security)
        price = bar.close
        notional = price * order.quantity
        if order.side is OrderSide.BUY:
            self._buy(order, price, notional)
        else:
            self._sell(order, price, notional)
        fill = Fill(order=order, price=price, ts=bar.ts)
        self._fills.append(fill)
        return fill

    def _buy(self, order: Order, price: float, notional: float) -> None:
        if notional > self._cash:
            raise InsufficientFunds(f"need {notional:.2f}, have {self._cash:.2f}")
        existing = self._positions.get(order.security.symbol)
        if self._max_position_value is not None:
            held = existing.quantity * price if existing else 0.0
            if held + notional > self._max_position_value:
                raise RiskLimitExceeded(
                    f"position value would exceed {self._max_position_value:.2f}"
                )
        self._cash -= notional
        if existing is None:
            self._positions[order.security.symbol] = Position(
                order.security, order.quantity, price
            )
        else:
            total_qty = existing.quantity + order.quantity
            avg = (existing.cost_basis + notional) / total_qty
            self._positions[order.security.symbol] = Position(
                order.security, total_qty, avg
            )

    def _sell(self, order: Order, price: float, notional: float) -> None:
        existing = self._positions.get(order.security.symbol)
        held = existing.quantity if existing else 0
        if order.quantity > held:
            raise InsufficientHolding(f"selling {order.quantity}, hold {held}")
        self._cash += notional
        remaining = held - order.quantity
        if remaining == 0:
            del self._positions[order.security.symbol]
        else:
            # avg_price unchanged on a partial sale.
            assert existing is not None
            self._positions[order.security.symbol] = Position(
                order.security, remaining, existing.avg_price
            )
