"""Plain data for a game in progress. No rules live here; see engine.py."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

TOTAL_MILES = 2000
MAX_PARTY = 5
MAX_HEALTH = 100
LOG_LIMIT = 12


@dataclass
class Person:
    name: str
    health: int = MAX_HEALTH
    ailment: str | None = None
    alive: bool = True

    @property
    def status(self) -> str:
        if not self.alive:
            return "gone"
        if self.ailment:
            return self.ailment
        if self.health >= 80:
            return "good"
        if self.health >= 50:
            return "fair"
        if self.health >= 25:
            return "poor"
        return "very poor"


@dataclass
class Choice:
    id: str
    label: str


@dataclass
class View:
    """Everything a frontend needs to draw one screen and collect one input.

    ``input_type`` is one of ``choice`` (submit a ``Choice.id``), ``text``
    (submit any string) or ``number`` (submit a non-negative integer).
    """

    phase: str
    title: str
    text: str
    input_type: str
    choices: list[Choice] = field(default_factory=list)
    status: dict[str, Any] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GameState:
    seed: int
    phase: str = "setup_name"
    profession: str | None = None
    party: list[Person] = field(default_factory=list)
    money: int = 0
    supplies: dict[str, int] = field(
        default_factory=lambda: {
            "groceries": 0,
            "coffee": 0,
            "meds": 0,
            "parts": 0,
            "outfits": 0,
        }
    )
    week: int = 1
    miles: int = 0
    hustle: str = "steady"
    budget: str = "normal"
    car: int = MAX_HEALTH
    rent: int = 1200
    missed_rent: int = 0
    weekly_pay: int = 0
    unemployed_weeks: int = 0
    insurance: str | None = None
    loan_plan: str | None = None
    garnished: bool = False
    resume_ready: bool = False
    gigged_this_week: bool = False
    starving: bool = False
    landmarks_seen: list[int] = field(default_factory=list)
    price_mult: float = 1.0
    pending_item: str | None = None
    pending_event: str | None = None
    pending_target: str | None = None
    pending_landmark: int | None = None
    cause_of_death: str | None = None
    epitaph: str | None = None
    log: list[str] = field(default_factory=list)
    rng_state: list[Any] | None = None

    @property
    def leader(self) -> Person:
        return self.party[0]

    @property
    def living(self) -> list[Person]:
        return [p for p in self.party if p.alive]

    @property
    def employed(self) -> bool:
        return self.unemployed_weeks == 0

    def say(self, *messages: str) -> None:
        self.log.extend(messages)
        del self.log[:-LOG_LIMIT]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameState:
        data = dict(data)
        data["party"] = [Person(**p) for p in data.get("party", [])]
        return cls(**data)
