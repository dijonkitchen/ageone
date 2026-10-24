"""Kelly allocation: weights that maximize expected log growth, g(w) = r + wᵀ(μ − r) − ½ wᵀΣw.

A Kelly fraction c solves max wᵀ(μ − r) − (1 / 2c) wᵀΣw under the constraints (long only, total invested at most
max_total, each weight at most max_weight), rather than scaling a constrained full-Kelly answer. Unconstrained,
the answer is c Σ⁻¹(μ − r). See SPEC-2026-10-03-portfolio-kelly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 252


# Covariance


def ledoit_wolf(returns: np.ndarray) -> tuple[np.ndarray, float]:
    """Ledoit and Wolf's (2004) shrinkage of the sample covariance toward a scaled identity.

    returns is T x N (rows are dates). Returns the shrunk covariance and the shrinkage intensity in [0, 1].
    """
    x = np.asarray(returns, dtype=float)
    t, n = x.shape
    if t < 2:
        raise ValueError("need at least two observations for a covariance")
    x = x - x.mean(axis=0)
    sample = x.T @ x / t
    mu = np.trace(sample) / n
    target = mu * np.eye(n)
    d2 = float(((sample - target) ** 2).sum())
    if d2 == 0:
        return sample, 0.0
    # Average squared distance of each observation's outer product from the sample covariance.
    b2_bar = float(sum(((np.outer(row, row) - sample) ** 2).sum() for row in x) / t**2)
    shrinkage = min(b2_bar, d2) / d2
    return shrinkage * target + (1 - shrinkage) * sample, shrinkage


def daily_log_returns(history: pd.DataFrame, tickers: list[str], years: float, end: pd.Timestamp | None = None) -> pd.DataFrame:
    """Daily log returns (date x ticker) over the lookback, on the dates every ticker traded."""
    closes = history.pivot_table(index="date", columns="ticker", values="close").sort_index()
    closes = closes.reindex(columns=tickers)
    end = end or (closes.index.max() if len(closes) else pd.Timestamp.today())
    closes = closes[closes.index >= end - pd.DateOffset(days=round(365.25 * years))]
    return np.log(closes).diff().dropna(how="any")


def covariance(history: pd.DataFrame, tickers: list[str], years: float = 5.0) -> tuple[np.ndarray, float, int]:
    """Annualized, shrunk covariance of daily log returns; also the shrinkage and the number of days used."""
    returns = daily_log_returns(history, tickers, years)
    if len(returns) < 2:
        raise ValueError(f"not enough overlapping price history for {', '.join(tickers)}")
    shrunk, shrinkage = ledoit_wolf(returns.to_numpy())
    return shrunk * TRADING_DAYS, shrinkage, len(returns)


def historical_mean_return(history: pd.DataFrame, ticker: str, years: float = 5.0) -> float:
    """Mean simple daily price return over the lookback, annualized (no dividends)."""
    closes = history[history["ticker"] == ticker].sort_values("date").set_index("date")["close"]
    if len(closes) < 2:
        return math.nan
    closes = closes[closes.index >= closes.index.max() - pd.DateOffset(days=round(365.25 * years))]
    return float(closes.pct_change().dropna().mean() * TRADING_DAYS)


def fundamentals_return(yield_: float, growth: float, cap: float = 0.10) -> float:
    """Expected return implied by fundamentals: a yield (FCF or earnings over price) plus per-share growth,
    with growth capped (a missing growth rate counts as zero)."""
    if yield_ is None or math.isnan(yield_):
        return math.nan
    growth = 0.0 if growth is None or math.isnan(growth) else min(growth, cap)
    return yield_ + growth


# Solver


@dataclass(frozen=True)
class Constraints:
    long_only: bool = True
    max_total: float | None = 1.0  # total invested; above 1 is leverage, the rest is cash
    max_weight: float | None = None  # per holding


LONG_ONLY = Constraints()


def unconstrained(mu: np.ndarray, cov: np.ndarray, r: float, fraction: float = 1.0) -> np.ndarray:
    """c Σ⁻¹(μ − r); with a singular Σ, the least-norm solution (pseudo-inverse)."""
    excess = np.asarray(mu, dtype=float) - r
    return fraction * np.linalg.pinv(np.asarray(cov, dtype=float), hermitian=True) @ excess


def _project(v: np.ndarray, lower: float, upper: np.ndarray, total: float | None) -> np.ndarray:
    """Euclidean projection onto {lower <= w <= upper, sum(w) <= total}."""
    w = np.clip(v, lower, upper)
    if total is None or w.sum() <= total:
        return w
    lo, hi = 0.0, float(np.max(v) - lower) + 1.0
    for _ in range(200):  # sum(clip(v - θ)) falls as θ grows; bisect for the θ that meets the budget
        mid = (lo + hi) / 2
        if np.clip(v - mid, lower, upper).sum() > total:
            lo = mid
        else:
            hi = mid
    return np.clip(v - hi, lower, upper)


def solve(mu, cov, r: float, fraction: float = 1.0, constraints: Constraints = LONG_ONLY,
          tol: float = 1e-12, max_iter: int = 200_000) -> np.ndarray:
    """Weights maximizing wᵀ(μ − r) − (1 / 2c) wᵀΣw under the constraints.

    A concave quadratic program over a box and a budget, solved by accelerated projected gradient (FISTA with
    restarts); projection onto that set is exact, so the answer is feasible and deterministic.
    """
    mu = np.asarray(mu, dtype=float)
    cov = np.asarray(cov, dtype=float)
    n = len(mu)
    if fraction <= 0:
        raise ValueError("the Kelly fraction must be above zero")
    lower = 0.0 if constraints.long_only else -np.inf
    upper = np.full(n, np.inf if constraints.max_weight is None else constraints.max_weight)
    if not constraints.long_only and constraints.max_total is None and constraints.max_weight is None:
        return unconstrained(mu, cov, r, fraction)
    excess = mu - r
    hessian = cov / fraction
    lipschitz = max(float(np.linalg.eigvalsh(hessian).max()), 1e-12)
    step = 1 / lipschitz
    w = _project(np.zeros(n), lower, upper, constraints.max_total)
    y, momentum = w.copy(), 1.0

    def objective(x):
        return float(x @ excess - 0.5 * x @ hessian @ x)

    for _ in range(max_iter):
        nxt = _project(y + step * (excess - hessian @ y), lower, upper, constraints.max_total)
        if np.max(np.abs(nxt - w)) < tol:
            w = nxt
            break
        if objective(nxt) < objective(w) - 1e-15:  # restart the momentum when it overshoots
            momentum, y = 1.0, w.copy()
            continue
        grown = (1 + math.sqrt(1 + 4 * momentum**2)) / 2
        y = nxt + ((momentum - 1) / grown) * (nxt - w)
        momentum = grown
        w = nxt
    return np.where(np.abs(w) < 1e-12, 0.0, w)


def growth(w: np.ndarray, mu: np.ndarray, cov: np.ndarray, r: float) -> dict[str, float]:
    """Expected return, volatility, and expected log growth of a portfolio with the rest in cash at r."""
    w = np.asarray(w, dtype=float)
    excess = np.asarray(mu, dtype=float) - r
    variance = float(w @ cov @ w)
    expected = r + float(w @ excess)
    return {"expected_return": expected, "volatility": math.sqrt(max(variance, 0.0)), "growth": expected - variance / 2}


@dataclass
class Allocation:
    holdings: pd.DataFrame  # ticker, mu, weight, dollars, shares, cost, held, trade, current_weight, weight_if_lower
    cash: float
    invested: float
    chosen: dict[str, float]
    full: dict[str, float]
    full_weights: np.ndarray


def allocate(tickers: list[str], mu, cov, prices, r: float, value: float, fraction: float = 0.5,
             constraints: Constraints = LONG_ONLY, held: list[float | None] | None = None,
             shift: float = 0.02) -> Allocation:
    """Weights, dollars, and whole shares for a portfolio value, the cash left, stats at full and chosen fraction,
    the trades from the shares held, and the weights if every μ were `shift` lower (the sensitivity view)."""
    mu = np.asarray(mu, dtype=float)
    prices = np.asarray(prices, dtype=float)
    weights = solve(mu, cov, r, fraction, constraints)
    full = solve(mu, cov, r, 1.0, constraints)
    lower = solve(mu - shift, cov, r, fraction, constraints)
    dollars = weights * value
    with np.errstate(all="ignore"):
        shares = np.where(prices > 0, np.floor(dollars / prices + 1e-9), np.nan)
    cost = shares * prices
    held_arr = np.array([np.nan if h is None else h for h in (held or [None] * len(tickers))], dtype=float)
    holdings = pd.DataFrame({
        "ticker": tickers, "mu": mu, "price": prices, "weight": weights, "dollars": dollars, "shares": shares,
        "cost": cost, "held": held_arr, "trade": shares - np.nan_to_num(held_arr),
        "current_weight": held_arr * prices / value if value else np.nan, "weight_if_lower": lower,
    })
    spent = float(np.nansum(cost))
    return Allocation(holdings, value - spent, spent, growth(weights, mu, cov, r), growth(full, mu, cov, r), full)
