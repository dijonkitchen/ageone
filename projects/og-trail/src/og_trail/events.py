"""Random events on the trail.

An ``Event`` either applies immediately (``apply``) or presents ``options`` for
the player to choose from. Content functions receive the ``Game`` so they can
read state and draw from its seeded RNG.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import Game
    from .state import Person

Text = str | Callable[["Game"], str]
Effect = Callable[["Game"], None]
Predicate = Callable[["Game"], bool]


def always(_: Game) -> bool:
    return True


@dataclass(frozen=True)
class Option:
    id: str
    label: str
    apply: Effect
    when: Predicate = always


@dataclass(frozen=True)
class Event:
    id: str
    weight: int
    title: str
    text: Text
    when: Predicate = always
    apply: Effect | None = None
    options: tuple[Option, ...] = ()
    pick: Callable[[Game], str | None] = lambda g: None
    weight_fn: Callable[[Game], float] = field(default=lambda g: 1.0)

    def weight_for(self, game: Game) -> float:
        return self.weight * self.weight_fn(game) if self.when(game) else 0.0

    def render(self, game: Game) -> str:
        return self.text(game) if callable(self.text) else self.text


AILMENTS = ("a cold", "the flu", "a mystery stomach thing", "the thing that's going around")
MEDICAL_BILL = {"gold": 0, "bronze": 150, "none": 600}
CAR_TOW = 350
CAR_DAMAGE = 30
WEDDING_COST = 600
PARTY_COST = 150
DENTIST_COST = 300
CRYPTO_STAKE = 500


def _random_living(game: Game) -> Person:
    return game.rng.choice(game.state.living)


def _companion_name(game: Game) -> str:
    others = [p for p in game.state.living if p is not game.state.leader]
    return game.rng.choice(others).name if others else "your old roommate"


def _spend(game: Game, amount: int) -> int:
    """Charge what can be charged and return what was actually paid."""
    paid = min(game.state.money, amount)
    game.state.money -= paid
    return paid


def _heal_all(game: Game, amount: int) -> None:
    for p in game.state.living:
        p.health = max(1, min(100, p.health + amount))


def rent_hike(game: Game) -> None:
    s = game.state
    s.rent = round(s.rent * (1 + game.rng.randint(5, 15) / 100))
    s.say(f"Your landlord 'adjusted' the rent. It is now ${s.rent:,}.")


def subscription(game: Game) -> None:
    cost = game.rng.randint(8, 79)
    _spend(game, cost)
    game.state.say(f"A subscription you forgot about renewed for ${cost}.")


def parking_ticket(game: Game) -> None:
    _spend(game, 75)
    game.state.say("Parking ticket. The sign was ambiguous. $75.")


def free_food(game: Game) -> None:
    meals = game.rng.randint(5, 15)
    game.state.supplies["groceries"] += meals
    game.state.say(f"Someone left a sheet cake in the break room. +{meals} meals.")


def tax_refund(game: Game) -> None:
    amount = game.rng.randint(200, 900)
    game.state.money += amount
    game.state.say(f"Tax refund! ${amount}. It was your money the whole time.")


def cold(game: Game) -> None:
    s = game.state
    healthy = [p for p in s.living if not p.ailment]
    if not healthy:
        return
    p = game.rng.choice(healthy)
    p.ailment = game.rng.choice(AILMENTS)
    bill = MEDICAL_BILL.get(s.insurance or "", 0)
    paid = _spend(game, bill)
    note = f" Urgent care billed ${paid}." if paid else ""
    s.say(f"{p.name} caught {p.ailment}.{note}")


def burnout(game: Game) -> None:
    s = game.state
    p = _random_living(game)
    if p.ailment:
        return
    p.ailment = "burnout"
    s.say(f"{p.name} is burned out. Everything is fine. Everything is fine.")


def doomscroll(game: Game) -> None:
    lost = game.rng.randint(20, 50)
    game.state.miles = max(0, game.state.miles - lost)
    game.state.say(f"You lost a weekend to doomscrolling. -{lost} miles.")


def wifi_outage(game: Game) -> None:
    game.state.miles = max(0, game.state.miles - 30)
    game.state.say("The Wi-Fi went out. You spent the week on hold with the ISP. -30 miles.")


def car_trouble(game: Game) -> None:
    s = game.state
    if s.supplies["parts"] > 0:
        s.supplies["parts"] -= 1
        s.say("The car broke down. You had a spare part. Smug.")
        return
    s.car = max(0, s.car - CAR_DAMAGE)
    paid = _spend(game, CAR_TOW)
    if paid == CAR_TOW:
        s.say(f"The car broke down. No spare part. The tow was ${CAR_TOW}.")
    else:
        s.say("The car broke down. No spare part, no tow money. You pushed it.")


def recruiter_ghost(game: Game) -> None:
    game.state.say("A recruiter who said they were 'very excited' has vanished.")


def raccoon(game: Game) -> None:
    s = game.state
    lost = min(s.supplies["groceries"], game.rng.randint(5, 12))
    s.supplies["groceries"] -= lost
    s.say(f"A raccoon got into the groceries. -{lost} meals. It looked you in the eye.")


def found_money(game: Game) -> None:
    amount = game.rng.randint(10, 40)
    game.state.money += amount
    game.state.say(f"You found ${amount} in an old coat.")


def promotion(game: Game) -> None:
    s = game.state
    s.weekly_pay = round(s.weekly_pay * 1.1)
    s.say(f"Promotion! You now make ${s.weekly_pay}/week and attend more meetings.")


def garnishment(game: Game) -> None:
    game.state.garnished = True
    game.state.say("Your ignored student loans found you. Wages are now garnished 20%.")


def layoff(game: Game) -> None:
    s = game.state
    weeks = game.rng.randint(3, 6)
    if s.resume_ready:
        weeks = max(1, weeks // 2)
    s.unemployed_weeks = weeks
    s.say("Your company had a 'restructuring'. You are part of the structure no more.")


def wedding_go(game: Game) -> None:
    _spend(game, WEDDING_COST)
    _heal_all(game, 10)
    game.state.say("The wedding was lovely. You cried at the vows. Worth it.")


def wedding_decline(game: Game) -> None:
    _heal_all(game, -5)
    game.state.say("You sent a gift. The group chat goes quiet.")


def dentist_fix(game: Game) -> None:
    _spend(game, DENTIST_COST)
    game.state.say(f"The filling cost ${DENTIST_COST}. The dentist asked about flossing.")


def dentist_ignore(game: Game) -> None:
    game.state.leader.ailment = "a toothache"
    game.state.say("You ignored the tooth. The tooth did not ignore you.")


def crypto_invest(game: Game) -> None:
    s = game.state
    _spend(game, CRYPTO_STAKE)
    if game.rng.random() < 0.1:
        s.money += CRYPTO_STAKE * 5
        s.say("Impossibly, the coin mooned. You are now insufferable about it.")
    else:
        s.say("The coin rugged. The Discord is gone. So is your $500.")


def crypto_ignore(game: Game) -> None:
    game.state.say("You did not buy the coin. This was correct.")


def birthday_party(game: Game) -> None:
    _spend(game, PARTY_COST)
    _heal_all(game, 8)
    game.state.say("You threw a party. Someone brought a cake with a name misspelled on it.")


def birthday_post(game: Game) -> None:
    _heal_all(game, 2)
    game.state.say("You posted a story. It got the heart emoji from three people.")


def venmo_pay(game: Game) -> None:
    _spend(game, 60)
    game.state.say("You paid the $60. You still don't know what 'the thing' was.")


def venmo_ignore(game: Game) -> None:
    _heal_all(game, -3)
    game.state.say("You left it on read. You are now the villain of the group chat.")


def can_afford(amount: int) -> Predicate:
    return lambda game: game.state.money >= amount


EVENTS: tuple[Event, ...] = (
    Event("rent_hike", 3, "Rent", "", apply=rent_hike),
    Event("subscription", 4, "Subscription", "", apply=subscription),
    Event("parking_ticket", 3, "Ticket", "", apply=parking_ticket),
    Event("free_food", 4, "Free food", "", apply=free_food),
    Event("tax_refund", 1, "Refund", "", apply=tax_refund),
    Event("cold", 5, "Sick", "", apply=cold),
    Event(
        "burnout",
        3,
        "Burnout",
        "",
        apply=burnout,
        weight_fn=lambda g: 3.0 if g.state.hustle == "grind" else 1.0,
    ),
    Event("doomscroll", 3, "Doomscroll", "", apply=doomscroll),
    Event("wifi_outage", 2, "Wi-Fi", "", apply=wifi_outage),
    Event("car_trouble", 4, "Car", "", apply=car_trouble),
    Event("recruiter_ghost", 2, "Recruiter", "", apply=recruiter_ghost),
    Event("raccoon", 2, "Raccoon", "", apply=raccoon),
    Event("found_money", 2, "Coat", "", apply=found_money),
    Event(
        "promotion",
        1,
        "Promotion",
        "",
        when=lambda g: g.state.employed and g.state.hustle == "grind",
        apply=promotion,
    ),
    Event(
        "garnishment",
        3,
        "Loans",
        "",
        when=lambda g: g.state.loan_plan == "ignored" and not g.state.garnished,
        apply=garnishment,
    ),
    Event("layoff", 2, "Layoff", "", when=lambda g: g.state.employed, apply=layoff),
    Event(
        "wedding",
        2,
        "Save the date",
        lambda g: (
            f"{g.state.pending_target} is getting married across the country. "
            f"Flights, hotel, and a gift come to about ${WEDDING_COST}."
        ),
        pick=_companion_name,
        options=(
            Option("go", f"Go (${WEDDING_COST})", wedding_go, can_afford(WEDDING_COST)),
            Option("decline", "Send a gift and regrets", wedding_decline),
        ),
    ),
    Event(
        "dentist",
        2,
        "Tooth",
        "One of your teeth has started making its presence known.",
        options=(
            Option("fix", f"See the dentist (${DENTIST_COST})", dentist_fix),
            Option("ignore", "It is probably fine", dentist_ignore),
        ),
    ),
    Event(
        "crypto",
        1,
        "Opportunity",
        "A stranger on the internet has a can't-miss opportunity. The coin has a dog on it.",
        when=can_afford(CRYPTO_STAKE),
        options=(
            Option("invest", f"Invest ${CRYPTO_STAKE}", crypto_invest),
            Option("ignore", "Close the tab", crypto_ignore),
        ),
    ),
    Event(
        "birthday",
        2,
        "Birthday",
        lambda g: f"It's {g.state.pending_target}'s birthday.",
        pick=_companion_name,
        options=(
            Option("party", f"Throw a party (${PARTY_COST})", birthday_party),
            Option("post", "Post a story", birthday_post),
        ),
    ),
    Event(
        "venmo",
        2,
        "Venmo",
        lambda g: f"{g.state.pending_target} requested $60 for 'the thing'.",
        pick=_companion_name,
        options=(
            Option("pay", "Pay it", venmo_pay),
            Option("ignore", "Leave it on read", venmo_ignore),
        ),
    ),
)
EVENT_BY_ID = {e.id: e for e in EVENTS}
DEFAULT_EVENT_CHANCE = 0.6
