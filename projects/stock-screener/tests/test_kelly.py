import numpy as np
import pandas as pd
import pytest

from screener import kelly
from screener.kelly import Constraints

FREE = Constraints(long_only=False, max_total=None, max_weight=None)
MU = np.array([0.08, 0.10, 0.12])
SIGMA = np.array([0.15, 0.20, 0.30])
CORR = np.array([[1, 0.3, 0.2], [0.3, 1, 0.4], [0.2, 0.4, 1]])
COV = np.outer(SIGMA, SIGMA) * CORR
R = 0.03


def objective(w, mu, cov, r, c):
    return w @ (mu - r) - w @ cov @ w / (2 * c)


def test_single_asset_matches_closed_form():
    # f = (μ − r) / σ², below 100% so no constraint binds.
    assert kelly.solve([0.10], [[0.04]], 0.02, 0.4) == pytest.approx([0.4 * 0.08 / 0.04], abs=1e-9)
    assert kelly.solve([0.06], [[0.09]], 0.02) == pytest.approx([0.04 / 0.09], abs=1e-9)
    # Full Kelly would be 200%; long only at most 100% stops there.
    assert kelly.solve([0.10], [[0.04]], 0.02) == pytest.approx([1.0], abs=1e-9)


def test_many_assets_unconstrained_matches_closed_form():
    expected = np.linalg.solve(COV, MU - R)
    assert kelly.solve(MU, COV, R, 1.0, FREE) == pytest.approx(expected, abs=1e-12)
    assert kelly.unconstrained(MU, COV, R, 0.5) == pytest.approx(0.5 * expected, abs=1e-12)
    # A quarter Kelly is interior (all positive, total under 100%), so the constrained solver finds the same answer.
    assert kelly.solve(MU, COV, R, 0.25) == pytest.approx(0.25 * expected, abs=1e-8)


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("constraints", [Constraints(), Constraints(max_weight=0.3), Constraints(max_total=1.5, max_weight=0.6)])
def test_constrained_answers_respect_constraints_and_are_optimal(seed, constraints):
    rng = np.random.default_rng(seed)
    n = 5
    a = rng.standard_normal((n, n))
    cov = a @ a.T / n * 0.05 + np.eye(n) * 0.01
    mu = rng.uniform(-0.05, 0.25, n)
    w = kelly.solve(mu, cov, R, 0.5, constraints)
    assert (w >= 0).all()
    assert w.sum() <= constraints.max_total + 1e-9
    if constraints.max_weight:
        assert (w <= constraints.max_weight + 1e-9).all()
    best = objective(w, mu, cov, R, 0.5)
    # No feasible point nearby or at random does better.
    for _ in range(2000):
        x = np.clip(w + rng.normal(0, 0.05, n), 0, constraints.max_weight or np.inf)
        if x.sum() > constraints.max_total:
            x *= constraints.max_total / x.sum()
        assert objective(x, mu, cov, R, 0.5) <= best + 1e-10


def test_fraction_solves_the_fractional_problem_not_a_scaled_answer():
    # Full Kelly wants far more than 100%, so the budget binds at both fractions.
    mu = np.array([0.20, 0.25])
    cov = np.array([[0.04, 0.01], [0.01, 0.09]])
    full = kelly.solve(mu, cov, R, 1.0)
    half = kelly.solve(mu, cov, R, 0.5)
    assert full.sum() == pytest.approx(1.0) and half.sum() == pytest.approx(1.0)
    assert not np.allclose(half, 0.5 * full)
    assert objective(half, mu, cov, R, 0.5) > objective(0.5 * full, mu, cov, R, 0.5)
    # Unconstrained, the fractional problem's answer is exactly c times full Kelly.
    assert kelly.solve(mu, cov, R, 0.5, FREE) == pytest.approx(0.5 * kelly.solve(mu, cov, R, 1.0, FREE))


def test_singular_and_near_singular_covariance():
    # Two copies of one asset: only the total is determined, and it matches the single-asset answer.
    cov = np.array([[0.04, 0.04], [0.04, 0.04]])
    w = kelly.solve([0.10, 0.10], cov, 0.02, 0.2)
    assert np.isfinite(w).all() and (w >= 0).all()
    assert w.sum() == pytest.approx(0.2 * 0.08 / 0.04, abs=1e-8)
    assert kelly.unconstrained([0.10, 0.10], cov, 0.02, 0.2).sum() == pytest.approx(0.4)
    near = np.array([[0.04, 0.04 * 0.999999], [0.04 * 0.999999, 0.04]])
    w = kelly.solve([0.10, 0.11], near, 0.02, 0.5)
    assert np.isfinite(w).all() and (w >= 0).all() and w.sum() <= 1 + 1e-9
    assert kelly.solve([0.10, 0.11], near, 0.02, 0.5) == pytest.approx(w)  # deterministic


def test_ledoit_wolf_shrinks_toward_scaled_identity():
    rng = np.random.default_rng(0)
    # More assets than days: the sample covariance is singular, the shrunk one is not.
    short = rng.standard_normal((10, 20)) * 0.01
    shrunk, intensity = kelly.ledoit_wolf(short)
    assert 0 < intensity <= 1
    assert np.linalg.eigvalsh(shrunk).min() > 0
    # Plenty of data from a very non-spherical covariance: little shrinkage.
    true = np.diag([0.04, 0.0001, 0.01])
    long = rng.multivariate_normal(np.zeros(3), true, size=5000)
    shrunk, intensity = kelly.ledoit_wolf(long)
    assert intensity < 0.05
    assert np.diag(shrunk) == pytest.approx(np.diag(true), rel=0.2)


def test_covariance_from_prices_is_annualized(prices_dir):
    history = pd.concat(pd.read_csv(prices_dir / f"{t}.prices.csv", parse_dates=["date"]).assign(ticker=t) for t in ("FAST", "SLOW"))
    cov, intensity, days = kelly.covariance(history, ["FAST", "SLOW"], 5)
    assert 1200 < days < 1320
    # Synthetic volatilities are 30% and 15%.
    assert np.sqrt(np.diag(cov)) == pytest.approx([0.30, 0.15], rel=0.1)
    assert 0 <= intensity <= 1


def test_allocate_whole_shares_cash_trades_and_sensitivity():
    a = kelly.allocate(["A", "B", "C"], MU, COV, [33.0, 120.0, 7.5], R, 10_000, 0.25, held=[10, None, 0], shift=0.02)
    h = a.holdings
    assert (h["shares"] == np.floor(h["dollars"] / h["price"])).all()
    assert a.cash == pytest.approx(10_000 - (h["shares"] * h["price"]).sum())
    assert h["trade"].tolist() == (h["shares"] - [10, 0, 0]).tolist()
    assert h["current_weight"].iloc[0] == pytest.approx(330 / 10_000)
    assert h["weight_if_lower"].sum() < h["weight"].sum()
    assert a.chosen["growth"] <= a.full["growth"] + 1e-12
    assert a.chosen["volatility"] < a.full["volatility"]


def test_return_suggestions():
    assert kelly.fundamentals_return(0.05, 0.25, cap=0.10) == pytest.approx(0.15)
    assert kelly.fundamentals_return(0.05, float("nan")) == pytest.approx(0.05)
    assert np.isnan(kelly.fundamentals_return(float("nan"), 0.05))
