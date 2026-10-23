"""Multi-year per-share history and growth (Spec 0004).

Turns a series of annual :class:`Financials` into per-share metrics, year-over-
year growth, and a median growth across the window (plus CAGR as a more
outlier-robust companion). Pure — callers supply the financial series.

Growth is reported as ``None`` when the prior value is non-positive, because a
percentage change off a zero/negative base is meaningless (e.g. a swing from a
loss to a profit).
"""

from __future__ import annotations

import itertools
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date

from ..domain import Financials

#: Per-share metrics tracked over time.
PER_SHARE_METRICS = (
    "revenue",
    "earnings",  # net income per share (EPS)
    "free_cash_flow",
    "book_value",  # shareholders' equity per share
    "operating_cash_flow",
)


@dataclass(frozen=True, slots=True)
class PerShare:
    """One fiscal period expressed per share."""

    period_end: date
    revenue: float
    earnings: float
    free_cash_flow: float
    book_value: float
    operating_cash_flow: float

    @classmethod
    def from_financials(cls, fin: Financials) -> PerShare:
        shares = fin.shares_outstanding
        return cls(
            period_end=fin.period_end,
            revenue=fin.revenue / shares,
            earnings=fin.net_income / shares,
            free_cash_flow=fin.free_cash_flow / shares,
            book_value=fin.shareholders_equity / shares,
            operating_cash_flow=fin.operating_cash_flow / shares,
        )

    def get(self, metric: str) -> float:
        value: float = getattr(self, metric)
        return value


@dataclass(frozen=True, slots=True)
class GrowthSummary:
    """Per-share values and growth for a single metric across the window."""

    metric: str
    periods: tuple[date, ...]
    per_share: tuple[float, ...]
    yoy_growth: tuple[float | None, ...]  # aligned to periods; first is None
    median_growth: float | None
    cagr: float | None


@dataclass(frozen=True, slots=True)
class FundamentalHistory:
    symbol: str
    rows: tuple[PerShare, ...]  # chronological, oldest first
    summaries: dict[str, GrowthSummary]

    @property
    def periods(self) -> tuple[date, ...]:
        return tuple(r.period_end for r in self.rows)


def yoy_growth(values: Sequence[float]) -> list[float | None]:
    """Year-over-year growth, ``None`` where the prior value is non-positive."""
    out: list[float | None] = [None]
    for prev, cur in itertools.pairwise(values):
        out.append(cur / prev - 1.0 if prev > 0 else None)
    return out


def median_growth(growth: Iterable[float | None]) -> float | None:
    clean = [g for g in growth if g is not None]
    return statistics.median(clean) if clean else None


def cagr(values: Sequence[float], periods: Sequence[date]) -> float | None:
    """Compound annual growth between the first and last positive value."""
    if len(values) < 2:
        return None
    first, last = values[0], values[-1]
    if first <= 0 or last <= 0:
        return None
    years = (periods[-1] - periods[0]).days / 365.25
    if years <= 0:
        return None
    growth: float = (last / first) ** (1.0 / years) - 1.0
    return growth


def build_history(
    financials: Iterable[Financials], *, years: int = 10
) -> FundamentalHistory:
    """Build a per-share history from annual financials (uses the last ``years``)."""
    series = sorted(financials, key=lambda f: f.period_end)
    if not series:
        raise ValueError("need at least one period of financials")
    series = series[-years:]
    rows = tuple(PerShare.from_financials(f) for f in series)
    periods = tuple(r.period_end for r in rows)

    summaries: dict[str, GrowthSummary] = {}
    for metric in PER_SHARE_METRICS:
        per_share = tuple(r.get(metric) for r in rows)
        growth = yoy_growth(per_share)
        summaries[metric] = GrowthSummary(
            metric=metric,
            periods=periods,
            per_share=per_share,
            yoy_growth=tuple(growth),
            median_growth=median_growth(growth),
            cagr=cagr(per_share, periods),
        )
    return FundamentalHistory(symbol=series[-1].symbol, rows=rows, summaries=summaries)
