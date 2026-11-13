"""Boundary protocols (ports).

Adapters implement these; the core depends only on the protocols, never on a
concrete vendor. Swapping a data feed or broker means writing a new adapter.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from .domain import Bar, Fill, Financials, OptionQuote, Order, Position, Security


@runtime_checkable
class MarketDataProvider(Protocol):
    """Read-only access to price history for a universe of securities."""

    def universe(self) -> Sequence[Security]: ...

    def history(self, security: Security, *, limit: int | None = None) -> Sequence[Bar]:
        """Bars in chronological order; the most recent last."""
        ...

    def latest(self, security: Security) -> Bar: ...


@runtime_checkable
class Broker(Protocol):
    """Order submission and account state."""

    @property
    def cash(self) -> float: ...

    def submit(self, order: Order) -> Fill: ...

    def positions(self) -> Sequence[Position]: ...


@runtime_checkable
class FundamentalsProvider(Protocol):
    """Access to a company's latest financial statements."""

    def financials(self, security: Security) -> Financials: ...


@runtime_checkable
class FundamentalsHistoryProvider(Protocol):
    """Access to multiple years of a company's financials (oldest first)."""

    def history(
        self, security: Security, *, years: int = 10
    ) -> Sequence[Financials]: ...


@runtime_checkable
class OptionQuoteProvider(Protocol):
    """The option chain (quotes for each contract) of an underlying."""

    def chain(self, underlying: Security) -> Sequence[OptionQuote]: ...
