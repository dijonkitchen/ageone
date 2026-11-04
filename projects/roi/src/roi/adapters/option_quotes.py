"""An in-memory ``OptionQuoteProvider`` for tests and demos.

A live chain (e.g. OpenBB's options endpoints) would be another adapter
implementing the same port; the pricing/alignment core never changes.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ..domain import OptionQuote, Security


class InMemoryOptionQuotes:
    """Serves pre-loaded option chains keyed by underlying symbol."""

    def __init__(self, quotes: Iterable[OptionQuote]) -> None:
        self._by_underlying: dict[str, list[OptionQuote]] = {}
        for quote in quotes:
            self._by_underlying.setdefault(quote.contract.underlying, []).append(quote)

    def chain(self, underlying: Security) -> Sequence[OptionQuote]:
        return tuple(self._by_underlying.get(underlying.symbol, ()))
