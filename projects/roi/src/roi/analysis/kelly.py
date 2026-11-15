"""Kelly-criterion position sizing (Spec 0004).

The continuous Kelly fraction for an asset is its expected excess return over
its return variance, ``f = mu / sigma**2``. Full Kelly is notoriously
aggressive, so allocations default to a fractional (half-Kelly) multiplier, are
long-only, and never lever past the provided total.

v0 treats assets as independent (diagonal covariance); a full covariance Kelly
needs linear algebra and is left as future work.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AssetEstimate:
    symbol: str
    expected_return: float  # expected excess return over the horizon
    volatility: float  # standard deviation of returns over the same horizon


@dataclass(frozen=True, slots=True)
class Allocation:
    symbol: str
    weight: float
    amount: float


def kelly_fraction(expected_return: float, volatility: float) -> float:
    """Continuous Kelly fraction ``mu / sigma**2``."""
    if volatility <= 0:
        raise ValueError("volatility must be positive")
    return expected_return / volatility**2


def kelly_allocations(
    estimates: Iterable[AssetEstimate],
    total: float,
    *,
    kelly_multiplier: float = 0.5,
    max_weight: float | None = None,
    allow_short: bool = False,
) -> list[Allocation]:
    """Weight ``total`` across assets by (fractional) Kelly.

    Weights are clamped to ``[0, max_weight]`` (long-only unless
    ``allow_short``) and scaled down if their gross would exceed 1, so the book
    is never levered. Any unallocated weight is implicitly held as cash.
    """
    if total < 0:
        raise ValueError("total must be non-negative")

    weights: dict[str, float] = {}
    for est in estimates:
        f = kelly_fraction(est.expected_return, est.volatility) * kelly_multiplier
        if not allow_short:
            f = max(f, 0.0)
        if max_weight is not None:
            f = min(f, max_weight)
        weights[est.symbol] = f

    gross = sum(abs(w) for w in weights.values())
    if gross > 1.0:
        weights = {sym: w / gross for sym, w in weights.items()}

    return [Allocation(sym, w, w * total) for sym, w in weights.items()]


def gross_exposure(allocations: Sequence[Allocation]) -> float:
    return sum(abs(a.weight) for a in allocations)
