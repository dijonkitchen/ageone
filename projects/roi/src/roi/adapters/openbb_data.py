"""An OpenBB-backed ``MarketDataProvider`` (optional dependency).

OpenBB is itself a multi-vendor abstraction, so this single adapter reaches
many data sources (yfinance, Polygon, FMP, Tiingo, ...) via its ``provider``
argument. It is the one place in ``roi`` that performs network I/O.

Install the optional dependency to use it::

    uv sync --extra openbb

The ``openbb`` import is deferred to call time, and the client is injectable,
so importing this module (and the rest of ``roi``) never requires OpenBB and
the core test suite stays offline.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from typing import Any

from ..domain import Bar, Security


def _field(record: Any, name: str) -> Any:
    """Read a field from an OpenBB result, whether object- or dict-shaped."""
    if isinstance(record, Mapping):
        return record[name]
    return getattr(record, name)


def _to_datetime(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, date):
        return datetime(raw.year, raw.month, raw.day)
    if isinstance(raw, str):
        return datetime.fromisoformat(raw)
    raise TypeError(f"unsupported date value: {raw!r}")


def _as_iso(value: date | str | None) -> str | None:
    if value is None or isinstance(value, str):
        return value
    return value.isoformat()


class OpenBBMarketData:
    """Fetches historical bars through OpenBB. Implements ``MarketDataProvider``.

    Args:
        securities: the tracked universe.
        provider: OpenBB data provider name (e.g. ``"yfinance"``, ``"polygon"``).
        start_date / end_date: optional history bounds (``date`` or ISO string).
        client: an OpenBB ``obb`` client; injected in tests, lazily imported
            from ``openbb`` otherwise.
    """

    def __init__(
        self,
        securities: Iterable[Security],
        *,
        provider: str = "yfinance",
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        client: Any | None = None,
    ) -> None:
        self._securities = {s.symbol: s for s in securities}
        if not self._securities:
            raise ValueError("OpenBBMarketData needs at least one security")
        self._provider = provider
        self._start = _as_iso(start_date)
        self._end = _as_iso(end_date)
        self._client = client
        self._cache: dict[str, list[Bar]] = {}

    def _obb(self) -> Any:
        if self._client is None:
            from openbb import obb  # ty: ignore[unresolved-import]  # optional dep

            self._client = obb
        return self._client

    def _fetch(self, security: Security) -> list[Bar]:
        cached = self._cache.get(security.symbol)
        if cached is not None:
            return cached
        response = self._obb().equity.price.historical(
            symbol=security.symbol,
            start_date=self._start,
            end_date=self._end,
            provider=self._provider,
        )
        bars = [self._to_bar(r) for r in response.results]
        bars.sort(key=lambda b: b.ts)  # chronological, most recent last
        if not bars:
            raise LookupError(f"no bars returned for {security.symbol}")
        self._cache[security.symbol] = bars
        return bars

    @staticmethod
    def _to_bar(record: Any) -> Bar:
        return Bar(
            ts=_to_datetime(_field(record, "date")),
            open=float(_field(record, "open")),
            high=float(_field(record, "high")),
            low=float(_field(record, "low")),
            close=float(_field(record, "close")),
            volume=int(_field(record, "volume")),
        )

    def universe(self) -> Sequence[Security]:
        return tuple(self._securities.values())

    def history(self, security: Security, *, limit: int | None = None) -> Sequence[Bar]:
        bars = self._fetch(security)
        return tuple(bars[-limit:]) if limit is not None else tuple(bars)

    def latest(self, security: Security) -> Bar:
        return self._fetch(security)[-1]
