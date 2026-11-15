"""An in-memory ``MarketDataProvider`` for tests, demos, and fixtures."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..domain import Bar, Security


class InMemoryMarketData:
    """Serves pre-loaded bars. Implements :class:`roi.ports.MarketDataProvider`."""

    def __init__(self, bars: Mapping[Security, Sequence[Bar]]) -> None:
        self._bars: dict[str, list[Bar]] = {}
        self._securities: dict[str, Security] = {}
        for security, series in bars.items():
            if not series:
                raise ValueError(f"{security.symbol} has no bars")
            self._securities[security.symbol] = security
            self._bars[security.symbol] = list(series)

    def universe(self) -> Sequence[Security]:
        return tuple(self._securities.values())

    def history(self, security: Security, *, limit: int | None = None) -> Sequence[Bar]:
        series = self._bars[security.symbol]
        if limit is not None:
            return tuple(series[-limit:])
        return tuple(series)

    def latest(self, security: Security) -> Bar:
        return self._bars[security.symbol][-1]
