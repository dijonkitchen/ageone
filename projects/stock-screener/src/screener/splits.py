"""Stock split adjustment.

Filers restate share counts and per-share values for a split, but only in the
filings after it, which cover the last two or three years. So a standardized
series holds restated values for recent years and as-reported values before,
and the split shows up as a jump between two consecutive years. We adjust
every year before that jump, so a year is never adjusted twice.

Candidate ratios come from split ratio tags where the filer tagged them;
otherwise a jump that matches a whole-number ratio (2:1, 3:1, 1:10 reverse)
counts as a split.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

import pandas as pd

TOLERANCE = 0.04  # how close a jump must be to the ratio
MIN_DETECTED_RATIO = 2


@dataclass(frozen=True)
class Split:
    fiscal_year: int  # first year on the new share basis
    ratio: float  # new shares per old share; below 1 for a reverse split
    source: str  # "tagged" or "detected"
    series: str  # which share series showed the jump


def _close(value: float, target: float) -> bool:
    return abs(value / target - 1) <= TOLERANCE


def _whole_ratio(jump: float) -> float | None:
    for value, invert in ((jump, False), (1 / jump, True)):
        n = round(value)
        if n >= MIN_DETECTED_RATIO and _close(value, n):
            return 1 / n if invert else float(n)
    return None


def detect(
    shares: pd.Series, tagged_ratios: list[float], series: str, per_share: pd.Series | None = None
) -> list[Split]:
    """Splits visible as jumps in a share count series indexed by fiscal year.

    per_share, when given, must move the opposite way at a detected (untagged)
    jump, which keeps a large share issuance from reading as a split.
    """
    shares = shares.dropna()
    shares = shares[shares > 0].sort_index()
    tagged = sorted({r for r in tagged_ratios if r > 0 and not _close(r, 1)})
    found: list[Split] = []
    years = list(shares.index)
    for previous, year in pairwise(years):
        jump = shares[year] / shares[previous]
        match = next((r for r in tagged if _close(jump, r)), None)
        if match is not None:
            found.append(Split(int(year), match, "tagged", series))
            continue
        ratio = _whole_ratio(jump)
        if ratio is None:
            continue
        if per_share is not None and previous in per_share and year in per_share:
            before, after = per_share[previous], per_share[year]
            if pd.notna(before) and pd.notna(after) and before != 0:
                moved = (after / before) * ratio
                # About 1 for a split (per-share value fell by the ratio), about the ratio for an issuance.
                if not 0.6 <= moved <= 1.6:
                    continue
        found.append(Split(int(year), ratio, "detected", series))
    return found


def factors(years: pd.Index, splits: list[Split]) -> pd.Series:
    """Cumulative ratio of splits after each year: multiply shares by it, divide per-share values."""
    out = pd.Series(1.0, index=years, dtype=float)
    for split in splits:
        out[out.index < split.fiscal_year] *= split.ratio
    return out
