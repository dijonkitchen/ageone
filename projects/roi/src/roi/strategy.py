"""Strategies turn market snapshots into signals (Spec 0003).

A ``Strategy`` is any ``Callable[[Sequence[Snapshot]], Sequence[Signal]]``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .domain import Action, Signal
from .screening import Snapshot

Strategy = Callable[[Sequence[Snapshot]], Sequence[Signal]]


@dataclass(frozen=True, slots=True)
class MomentumStrategy:
    """Buy strength when price is above its SMA with positive momentum;
    otherwise signal a sell. Securities without enough history are skipped."""

    sma_window: int = 50
    momentum_window: int = 20

    def __call__(self, snapshots: Sequence[Snapshot]) -> Sequence[Signal]:
        signals: list[Signal] = []
        need = max(self.sma_window, self.momentum_window + 1)
        for snap in snapshots:
            if len(snap.bars) < need:
                continue
            above = snap.price > snap.sma(self.sma_window)
            mom = snap.momentum(self.momentum_window)
            if above and mom > 0:
                signals.append(
                    Signal(
                        snap.security,
                        Action.BUY,
                        strength=min(mom, 1.0),
                        reason=f"above SMA{self.sma_window}, mom={mom:.3f}",
                    )
                )
            else:
                signals.append(Signal(snap.security, Action.SELL, reason="trend lost"))
        return signals
