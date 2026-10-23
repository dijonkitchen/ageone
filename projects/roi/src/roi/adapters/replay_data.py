"""A ``MarketDataProvider`` that reveals history one bar at a time.

The backtest harness drives this adapter: it starts with no bars revealed and
calls :meth:`advance` to step the clock. ``history`` and ``latest`` only ever
return bars up to the current cursor, so a strategy cannot peek at the future.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..domain import Bar, Security


class ReplayMarketData:
    def __init__(self, bars: Mapping[Security, Sequence[Bar]]) -> None:
        if not bars:
            raise ValueError("replay needs at least one security")
        self._securities: dict[str, Security] = {}
        self._bars: dict[str, list[Bar]] = {}
        lengths = set()
        for security, series in bars.items():
            if not series:
                raise ValueError(f"{security.symbol} has no bars")
            self._securities[security.symbol] = security
            self._bars[security.symbol] = list(series)
            lengths.add(len(series))
        if len(lengths) != 1:
            raise ValueError("all securities must share one aligned timeline")
        self._length = lengths.pop()
        self._cursor = 0  # number of bars revealed

    @property
    def timeline_length(self) -> int:
        return self._length

    @property
    def cursor(self) -> int:
        return self._cursor

    def advance(self) -> bool:
        """Reveal the next bar. Returns ``False`` once the timeline is spent."""
        if self._cursor >= self._length:
            return False
        self._cursor += 1
        return True

    def universe(self) -> Sequence[Security]:
        return tuple(self._securities.values())

    def history(self, security: Security, *, limit: int | None = None) -> Sequence[Bar]:
        revealed = self._bars[security.symbol][: self._cursor]
        if limit is not None:
            return tuple(revealed[-limit:])
        return tuple(revealed)

    def latest(self, security: Security) -> Bar:
        if self._cursor == 0:
            raise LookupError("no bars revealed yet; call advance() first")
        return self._bars[security.symbol][self._cursor - 1]
