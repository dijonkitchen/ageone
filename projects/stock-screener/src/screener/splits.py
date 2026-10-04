"""Stock split adjustment.

Filers restate share counts and per-share values for a split, but only in the
filings after it, which cover the last two or three years. So a standardized
series holds restated values for recent years and as-reported values before,
and the split shows up as a jump between two consecutive years. We adjust
every year before that jump, so a year is never adjusted twice.

Candidate ratios come from split ratio tags where the filer tagged them;
otherwise a jump that matches a whole-number ratio (2:1, 3:1, 1:10 reverse)
counts as a split. A tagged split is known to have happened, so its jump may
also carry a year of buybacks or issuance (Apple's 4:1 in 2020 shows as 3.72)
and gets a looser match, confirmed by the per-share value where there is one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise

import pandas as pd

TOLERANCE = 0.04  # how close a jump must be to the ratio
TAGGED_TOLERANCE = 0.15  # most a tagged split's jump may drift from its ratio
MIN_DETECTED_RATIO = 2


@dataclass(frozen=True)
class Split:
    fiscal_year: int  # first year on the new share basis
    ratio: float  # new shares per old share; below 1 for a reverse split
    source: str  # "tagged" or "detected"
    series: str  # which share series showed the jump


def _close(value: float, target: float, tolerance: float = TOLERANCE) -> bool:
    return abs(value / target - 1) <= tolerance


def _tagged_tolerance(ratio: float) -> float:
    # Scales with the split's size, so a small tagged ratio (a 10% stock dividend) can't absorb ordinary drift.
    return max(TOLERANCE, min(TAGGED_TOLERANCE, abs(math.log(ratio)) / 4))


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

    per_share, when given, must move the opposite way at a detected jump or a
    loosely matched tagged one, which keeps a large share issuance from reading
    as a split.
    """
    shares = shares.dropna()
    shares = shares[shares > 0].sort_index()
    tagged = sorted({r for r in tagged_ratios if r > 0 and not _close(r, 1)})
    found: list[Split] = []
    years = list(shares.index)
    for previous, year in pairwise(years):
        jump = shares[year] / shares[previous]
        match = next((r for r in tagged if _close(jump, r)), None)
        if match is None:
            loose = next((r for r in tagged if _close(jump, r, _tagged_tolerance(r))), None)
            if loose is not None and _per_share_agrees(per_share, previous, year, loose) is not False:
                match = loose
        if match is not None:
            found.append(Split(int(year), match, "tagged", series))
            continue
        ratio = _whole_ratio(jump)
        if ratio is None or _per_share_agrees(per_share, previous, year, ratio) is False:
            continue
        found.append(Split(int(year), ratio, "detected", series))
    return found


def _per_share_agrees(per_share: pd.Series | None, previous: int, year: int, ratio: float) -> bool | None:
    """Whether the per-share value moved the opposite way by about the ratio; None when it can't tell."""
    if per_share is None or previous not in per_share or year not in per_share:
        return None
    before, after = per_share[previous], per_share[year]
    if pd.isna(before) or pd.isna(after) or before == 0:
        return None
    moved = (after / before) * ratio
    # About 1 for a split (per-share value fell by the ratio), about the ratio for an issuance.
    return bool(0.6 <= moved <= 1.6)


def factors(years: pd.Index, splits: list[Split]) -> pd.Series:
    """Cumulative ratio of splits after each year: multiply shares by it, divide per-share values."""
    out = pd.Series(1.0, index=years, dtype=float)
    for split in splits:
        out[out.index < split.fiscal_year] *= split.ratio
    return out
