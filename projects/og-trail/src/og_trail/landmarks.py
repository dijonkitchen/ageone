"""Fixed stops along the trail: forts, river crossings, and their modern kin."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .events import Option, always, can_afford
from .state import TOTAL_MILES

if TYPE_CHECKING:
    from .engine import Game

LOAN_BALANCE = 2500
LOAN_WEEKLY = 40
PREMIUMS = {"gold": 120, "bronze": 30, "none": 0}
MOVING_COST = 1500
REUNION_COST = 300


@dataclass(frozen=True)
class Landmark:
    miles: int
    name: str
    text: str
    options: tuple[Option, ...] = ()
    price_mult: float = 1.0

    def choices_for(self, game: Game) -> list[Option]:
        return [o for o in self.options if o.when(game)]


def _say(game: Game, *lines: str) -> None:
    game.state.say(*lines)


def _heal_all(game: Game, amount: int) -> None:
    for p in game.state.living:
        p.health = max(1, min(100, p.health + amount))


def go_on(game: Game) -> None:
    pass


def shop(game: Game) -> None:
    game.state.phase = "store"


def loan_pay(game: Game) -> None:
    game.state.money -= LOAN_BALANCE
    game.state.loan_plan = "paid"
    _say(game, f"You paid off ${LOAN_BALANCE:,} of student loans. You feel nothing. Then relief.")


def loan_ibr(game: Game) -> None:
    game.state.loan_plan = "ibr"
    _say(game, f"Income-based repayment: ${LOAN_WEEKLY}/week, forever-ish.")


def loan_ignore(game: Game) -> None:
    game.state.loan_plan = "ignored"
    _say(game, "You put the letters in a drawer. The drawer is full.")


def insure(plan: str) -> Callable[[Game], None]:
    def apply(game: Game) -> None:
        game.state.insurance = plan
        _say(game, f"You picked the {plan} plan. ${PREMIUMS[plan]}/week.")

    return apply


def reunion_go(game: Game) -> None:
    game.state.money -= REUNION_COST
    _heal_all(game, 10)
    _say(game, "The reunion was great. Everyone is older and nicer than you remembered.")


def reunion_mute(game: Game) -> None:
    _heal_all(game, -5)
    _say(game, "You muted the chat. Someone noticed.")


def reunion_lol(game: Game) -> None:
    if game.rng.random() < 0.5:
        _heal_all(game, 5)
        _say(game, "'lol' landed. Nobody asked follow-up questions.")
    else:
        _heal_all(game, -10)
        game.state.money = max(0, game.state.money - 100)
        _say(game, "'lol' did not land. A surprise Venmo request for $100 arrived.")


def resume(game: Game) -> None:
    game.state.resume_ready = True
    _say(game, "You updated your résumé. It now says 'results-driven'.")


def head_down(game: Game) -> None:
    _say(game, "You kept your head down. The rumors keep circulating.")


def delete_apps(game: Game) -> None:
    _heal_all(game, 5)
    _say(game, "You deleted the apps. You reinstalled one. Still: progress.")


def scroll(game: Game) -> None:
    _heal_all(game, -10)
    if game.rng.random() < 0.3:
        game.state.money += 200
        _say(game, "You scrolled through it and somehow won a $200 giveaway.")
    else:
        _say(game, "You scrolled through it. You know too much now.")


def lease_sign(game: Game) -> None:
    game.state.rent = round(game.state.rent * 1.12)
    _say(game, f"You signed. Rent is now ${game.state.rent:,}.")


def lease_negotiate(game: Game) -> None:
    if game.rng.random() < 0.5:
        _say(game, "You negotiated. The landlord blinked. Rent stays the same.")
    else:
        game.state.rent = round(game.state.rent * 1.2)
        _say(game, f"You negotiated. The landlord did not blink. Rent is now ${game.state.rent:,}.")


def lease_move(game: Game) -> None:
    game.state.money -= MOVING_COST
    game.state.rent = round(game.state.rent * 0.85)
    _say(game, f"You moved. It cost ${MOVING_COST:,}. New rent: ${game.state.rent:,}.")


CONTINUE = Option("continue", "Continue", go_on, always)

LANDMARKS: tuple[Landmark, ...] = (
    Landmark(0, "Your Parents' Driveway", "Where it all begins."),
    Landmark(
        200,
        "First Paycheck Falls",
        "Your first real paycheck arrived. It is smaller than you expected. "
        "You look up what FICA is. You wish you had not.",
        (CONTINUE,),
    ),
    Landmark(
        400,
        "Student Loan Crossing",
        f"The letters have found your new address. Balance: ${LOAN_BALANCE:,}. You must cross.",
        (
            Option(
                "pay", f"Pay it in full (${LOAN_BALANCE:,})", loan_pay, can_afford(LOAN_BALANCE)
            ),
            Option("ibr", f"Income-based repayment (${LOAN_WEEKLY}/week)", loan_ibr),
            Option("ignore", "Put the letters in a drawer", loan_ignore),
        ),
    ),
    Landmark(
        600,
        "Fort Costco",
        "A warehouse the size of a county. Prices are up 25% since you left. Inflation.",
        (Option("shop", "Shop", shop), CONTINUE),
        price_mult=1.25,
    ),
    Landmark(
        800,
        "Open Enrollment Pass",
        "You have aged off your parents' health plan. Pick one. You have until Friday.",
        (
            Option("gold", f"Gold plan (${PREMIUMS['gold']}/week, no bills)", insure("gold")),
            Option(
                "bronze",
                f"Bronze plan (${PREMIUMS['bronze']}/week, $150 per visit)",
                insure("bronze"),
            ),
            Option("none", "No plan ($0/week, $600 per visit)", insure("none")),
        ),
    ),
    Landmark(
        1000,
        "The Great Group Chat",
        "A reunion is being planned. 214 unread messages. You must respond.",
        (
            Option("go", f"Go (${REUNION_COST})", reunion_go, can_afford(REUNION_COST)),
            Option("mute", "Mute the chat", reunion_mute),
            Option("lol", "Reply 'lol' and hope", reunion_lol),
        ),
    ),
    Landmark(
        1200,
        "Fort Target",
        "You came for toothpaste. Prices are up 50% since you left. You will leave with a lamp.",
        (Option("shop", "Shop", shop), CONTINUE),
        price_mult=1.5,
    ),
    Landmark(
        1400,
        "Layoff Gulch",
        "There are rumors of a restructuring. Leadership has scheduled an all-hands "
        "with no agenda.",
        (
            Option("resume", "Update your résumé", resume),
            Option("head_down", "Keep your head down", head_down),
        ),
    ),
    Landmark(
        1600,
        "Doomscroll Desert",
        "The news is bad and there is so much of it. The feed stretches to the horizon.",
        (
            Option("delete", "Delete the apps", delete_apps),
            Option("scroll", "Scroll through it", scroll),
        ),
    ),
    Landmark(
        1800,
        "Lease Renewal River",
        "Your lease is up. The renewal offer has a number on it that is not the old number.",
        (
            Option("sign", "Sign the renewal (+12% rent)", lease_sign),
            Option("negotiate", "Negotiate", lease_negotiate),
            Option(
                "move",
                f"Move somewhere cheaper (${MOVING_COST:,})",
                lease_move,
                can_afford(MOVING_COST),
            ),
        ),
    ),
    Landmark(TOTAL_MILES, "Stability", "A modest apartment with a dishwasher."),
)
LANDMARK_BY_MILES = {lm.miles: lm for lm in LANDMARKS}


def next_landmark(miles: int) -> Landmark:
    for lm in LANDMARKS:
        if lm.miles > miles:
            return lm
    return LANDMARKS[-1]
