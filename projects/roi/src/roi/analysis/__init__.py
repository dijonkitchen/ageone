"""Pure fundamental analysis: valuation, ratios, and allocation (Spec 0004).

Nothing here performs I/O — these functions take plain figures or domain
objects, so they are fully deterministic and testable.
"""

from .compare import CompanyAnalysis, analyze, annualized_volatility, kelly_estimates
from .dcf import DCFAssumptions, DCFResult, dcf, dcf_from_financials
from .history import (
    PER_SHARE_METRICS,
    FundamentalHistory,
    GrowthSummary,
    PerShare,
    build_history,
    cagr,
    median_growth,
    yoy_growth,
)
from .kelly import Allocation, AssetEstimate, kelly_allocations, kelly_fraction
from .ratios import KeyStats, key_stats

__all__ = [
    "PER_SHARE_METRICS",
    "Allocation",
    "AssetEstimate",
    "CompanyAnalysis",
    "DCFAssumptions",
    "DCFResult",
    "FundamentalHistory",
    "GrowthSummary",
    "KeyStats",
    "PerShare",
    "analyze",
    "annualized_volatility",
    "build_history",
    "cagr",
    "dcf",
    "dcf_from_financials",
    "kelly_allocations",
    "kelly_estimates",
    "kelly_fraction",
    "key_stats",
    "median_growth",
    "yoy_growth",
]
