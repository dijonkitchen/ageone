"""Orchestration: tickers -> financials + price -> stats + DCF -> comparison,
then Kelly estimates (Spec 0004).

Pure given its providers — the network lives entirely in the adapters passed in.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from ..domain import Bar, Financials, Security
from ..ports import FundamentalsProvider, MarketDataProvider
from .dcf import DCFAssumptions, DCFResult, dcf_from_financials
from .kelly import AssetEstimate
from .ratios import KeyStats, key_stats


@dataclass(frozen=True, slots=True)
class CompanyAnalysis:
    symbol: str
    price: float
    financials: Financials
    stats: KeyStats
    valuation: DCFResult
    upside: float  # intrinsic value / price - 1


def _as_security(ticker: str | Security) -> Security:
    return ticker if isinstance(ticker, Security) else Security(ticker)


def analyze(
    tickers: Iterable[str | Security],
    fundamentals: FundamentalsProvider,
    market: MarketDataProvider,
    assumptions: DCFAssumptions | None = None,
) -> list[CompanyAnalysis]:
    """Build a ranked (by upside, descending) comparison for the given tickers."""
    out: list[CompanyAnalysis] = []
    for ticker in tickers:
        security = _as_security(ticker)
        fin = fundamentals.financials(security)
        price = market.latest(security).close
        valuation = dcf_from_financials(fin, assumptions)
        upside = valuation.intrinsic_value_per_share / price - 1.0 if price else 0.0
        out.append(
            CompanyAnalysis(
                symbol=security.symbol,
                price=price,
                financials=fin,
                stats=key_stats(fin, price),
                valuation=valuation,
                upside=upside,
            )
        )
    out.sort(key=lambda c: c.upside, reverse=True)
    return out


def annualized_volatility(bars: Sequence[Bar], *, periods_per_year: int = 252) -> float:
    """Annualized stdev of simple period returns from a price series."""
    if len(bars) < 2:
        raise ValueError("need at least two bars to estimate volatility")
    returns = [bars[i].close / bars[i - 1].close - 1.0 for i in range(1, len(bars))]
    return statistics.pstdev(returns) * math.sqrt(periods_per_year)


def kelly_estimates(
    analyses: Iterable[CompanyAnalysis],
    market: MarketDataProvider,
    *,
    lookback: int = 252,
    periods_per_year: int = 252,
) -> list[AssetEstimate]:
    """Build Kelly inputs from each analysis: DCF upside as the expected return,
    historical annualized volatility as the risk. Illustrative defaults — supply
    your own estimates for real use."""
    estimates: list[AssetEstimate] = []
    for analysis in analyses:
        bars = market.history(Security(analysis.symbol), limit=lookback + 1)
        estimates.append(
            AssetEstimate(
                symbol=analysis.symbol,
                expected_return=analysis.upside,
                volatility=annualized_volatility(
                    bars, periods_per_year=periods_per_year
                ),
            )
        )
    return estimates
