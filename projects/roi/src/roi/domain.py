"""Pure, immutable value objects shared across the toolkit.

Nothing here performs I/O or depends on other ``roi`` modules, so these types
are safe to use from the core and the adapters alike.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class AssetKind(str, Enum):
    EQUITY = "equity"
    OPTION = "option"


class OptionRight(str, Enum):
    CALL = "call"
    PUT = "put"


class Action(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class OptionContract:
    """An options contract. v0 models the terms only — no pricing/greeks."""

    underlying: str
    expiry: date
    strike: float
    right: OptionRight


@dataclass(frozen=True, slots=True)
class Security:
    symbol: str
    kind: AssetKind = AssetKind.EQUITY
    option: OptionContract | None = None

    def __post_init__(self) -> None:
        if self.kind is AssetKind.OPTION and self.option is None:
            raise ValueError("option securities require an OptionContract")
        if self.kind is AssetKind.EQUITY and self.option is not None:
            raise ValueError("equity securities must not carry an OptionContract")


@dataclass(frozen=True, slots=True)
class Bar:
    """A single OHLCV price bar."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True, slots=True)
class Signal:
    security: Security
    action: Action
    strength: float = 1.0  # conviction in [0, 1]
    reason: str = ""


@dataclass(frozen=True, slots=True)
class Order:
    security: Security
    side: OrderSide
    quantity: int

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("order quantity must be positive")


@dataclass(frozen=True, slots=True)
class Fill:
    order: Order
    price: float
    ts: datetime


@dataclass(frozen=True, slots=True)
class Position:
    security: Security
    quantity: int
    avg_price: float

    @property
    def cost_basis(self) -> float:
        return self.quantity * self.avg_price


@dataclass(frozen=True, slots=True)
class Financials:
    """One fiscal period of company figures (e.g. from a 10-K)."""

    symbol: str
    period_end: date
    revenue: float
    net_income: float
    operating_cash_flow: float
    capital_expenditures: float  # positive magnitude of cash spent
    total_debt: float
    cash_and_equivalents: float
    shareholders_equity: float
    shares_outstanding: float

    def __post_init__(self) -> None:
        if self.shares_outstanding <= 0:
            raise ValueError("shares_outstanding must be positive")

    @property
    def free_cash_flow(self) -> float:
        return self.operating_cash_flow - self.capital_expenditures

    @property
    def net_debt(self) -> float:
        return self.total_debt - self.cash_and_equivalents

    @property
    def eps(self) -> float:
        return self.net_income / self.shares_outstanding


@dataclass(frozen=True, slots=True)
class OptionQuote:
    """A market quote for a single option contract."""

    security: Security  # must be an option
    bid: float
    ask: float
    last: float
    implied_volatility: float | None = None
    underlying_price: float | None = None

    def __post_init__(self) -> None:
        if self.security.kind is not AssetKind.OPTION or self.security.option is None:
            raise ValueError("OptionQuote requires an option security")

    @property
    def contract(self) -> OptionContract:
        assert self.security.option is not None  # guaranteed by __post_init__
        return self.security.option

    @property
    def mid(self) -> float:
        """Bid/ask midpoint, falling back to last when a side is missing."""
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2
        return self.last
