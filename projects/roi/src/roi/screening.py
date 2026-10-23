"""Composable, pure screening over market snapshots (Spec 0002)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from .domain import Bar, Security

Filter = Callable[["Snapshot"], bool]
Score = Callable[["Snapshot"], float]


@dataclass(frozen=True, slots=True)
class Snapshot:
    """A security together with its recent bars and derived metrics."""

    security: Security
    bars: Sequence[Bar]

    def __post_init__(self) -> None:
        if not self.bars:
            raise ValueError("a snapshot needs at least one bar")

    @property
    def last(self) -> Bar:
        return self.bars[-1]

    @property
    def price(self) -> float:
        return self.last.close

    def _window(self, window: int) -> Sequence[Bar]:
        if window <= 0:
            raise ValueError("window must be positive")
        if len(self.bars) < window:
            raise ValueError(
                f"need {window} bars for this metric, have {len(self.bars)}"
            )
        return self.bars[-window:]

    def sma(self, window: int) -> float:
        bars = self._window(window)
        return sum(b.close for b in bars) / len(bars)

    def avg_volume(self, window: int) -> float:
        bars = self._window(window)
        return sum(b.volume for b in bars) / len(bars)

    def momentum(self, window: int) -> float:
        """Simple return over ``window`` bars: close_now / close_then - 1."""
        bars = self._window(window + 1)
        then = bars[0].close
        if then == 0:
            raise ValueError("cannot compute momentum from a zero base price")
        return self.price / then - 1.0


# --- Filters (small, inspectable, reusable) --------------------------------


@dataclass(frozen=True, slots=True)
class PriceBetween:
    low: float
    high: float

    def __call__(self, snap: Snapshot) -> bool:
        return self.low <= snap.price <= self.high


@dataclass(frozen=True, slots=True)
class MinAvgVolume:
    minimum: float
    window: int = 20

    def __call__(self, snap: Snapshot) -> bool:
        return snap.avg_volume(self.window) >= self.minimum


@dataclass(frozen=True, slots=True)
class AboveSMA:
    window: int = 50

    def __call__(self, snap: Snapshot) -> bool:
        return snap.price > snap.sma(self.window)


@dataclass(frozen=True, slots=True)
class PositiveMomentum:
    window: int = 20

    def __call__(self, snap: Snapshot) -> bool:
        return snap.momentum(self.window) > 0.0


# --- Combinators -----------------------------------------------------------


def all_of(*filters: Filter) -> Filter:
    """Pass when every filter passes (vacuously true with no filters)."""
    return lambda snap: all(f(snap) for f in filters)


def any_of(*filters: Filter) -> Filter:
    """Pass when any filter passes (vacuously false with no filters)."""
    return lambda snap: any(f(snap) for f in filters)


def negate(f: Filter) -> Filter:
    return lambda snap: not f(snap)


# --- Screener --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScreenResult:
    snapshot: Snapshot
    score: float

    @property
    def security(self) -> Security:
        return self.snapshot.security


@dataclass(frozen=True, slots=True)
class Screener:
    filters: Sequence[Filter] = ()
    score: Score | None = None

    def run(self, snapshots: Iterable[Snapshot]) -> list[ScreenResult]:
        passed = [s for s in snapshots if all(f(s) for f in self.filters)]
        results = [
            ScreenResult(snapshot=s, score=self.score(s) if self.score else 0.0)
            for s in passed
        ]
        # Stable sort keeps input order for ties (Spec 0002).
        results.sort(key=lambda r: r.score, reverse=True)
        return results
