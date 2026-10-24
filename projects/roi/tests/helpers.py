"""Test fixtures: small, explicit, deterministic price series."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from roi.domain import Bar


def bars_from_closes(closes: Sequence[float], *, volume: int = 1_000_000) -> list[Bar]:
    """Build OHLCV bars from a list of closing prices (O=H=L=C)."""
    start = datetime(2024, 1, 1)
    return [
        Bar(start + timedelta(days=i), c, c, c, c, volume) for i, c in enumerate(closes)
    ]
