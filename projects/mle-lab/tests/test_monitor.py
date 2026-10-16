import numpy as np
import pandas as pd

from mle_lab.monitor import psi


def test_psi_is_near_zero_for_the_same_distribution() -> None:
    rng = np.random.default_rng(0)
    assert psi(pd.Series(rng.normal(size=5000)), pd.Series(rng.normal(size=5000))) < 0.02


def test_psi_flags_a_shift() -> None:
    rng = np.random.default_rng(0)
    assert psi(pd.Series(rng.normal(size=5000)), pd.Series(rng.normal(1, size=5000))) > 0.2


def test_psi_compares_rare_counts_value_by_value() -> None:
    """Deciles of a mostly-zero count collapse to one bin; per-value bins still see the shift."""
    reference = pd.Series([0] * 90 + [1] * 10)
    current = pd.Series([0] * 50 + [1] * 40 + [2] * 10)
    assert psi(reference, current) > 0.2


def test_psi_on_categories() -> None:
    assert psi(pd.Series(["a", "b"] * 50), pd.Series(["a"] * 90 + ["c"] * 10)) > 0.2
