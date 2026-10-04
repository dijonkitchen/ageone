"""Static game content: professions, items, and their flavor text."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Profession:
    id: str
    name: str
    money: int
    weekly_pay: int
    rent: int
    multiplier: int
    blurb: str


PROFESSIONS: tuple[Profession, ...] = (
    Profession(
        "tech",
        "Tech Worker",
        money=5000,
        weekly_pay=1000,
        rent=1400,
        multiplier=1,
        blurb="A one-bedroom with a gym. Comfortable, but one reorg away from a layoff.",
    ),
    Profession(
        "nurse",
        "Nurse",
        money=3000,
        weekly_pay=800,
        rent=1100,
        multiplier=2,
        blurb="Steady hands, brutal hours, decent benefits.",
    ),
    Profession(
        "barista",
        "Barista with a Podcast",
        money=1500,
        weekly_pay=550,
        rent=800,
        multiplier=3,
        blurb="A room in a house with four roommates. Rich in followers, poor in everything else.",
    ),
)
PROFESSION_BY_ID = {p.id: p for p in PROFESSIONS}


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    unit: str
    price: int
    blurb: str


ITEMS: tuple[Item, ...] = (
    Item(
        "groceries",
        "Groceries",
        "meals",
        4,
        "Everyone eats 5 to 10 meals a week, budget depending.",
    ),
    Item("coffee", "Coffee", "bags", 12, "Fuel for side gigs. One bag per gig."),
    Item(
        "meds",
        "Med kits",
        "kits",
        25,
        "Cures one sick traveler. Cold medicine, bandages, a therapist's number.",
    ),
    Item(
        "parts",
        "Car parts",
        "parts",
        120,
        "For when the check-engine light stops being theoretical.",
    ),
    Item(
        "outfits",
        "Interview outfits",
        "outfits",
        60,
        "For job hunting and weddings. Yes, you need one.",
    ),
)
ITEM_BY_ID = {i.id: i for i in ITEMS}

DEFAULT_LEADER = "Traveler"
DEFAULT_COMPANIONS = ("Priya", "Marcus", "Jules", "Theo")


@dataclass(frozen=True)
class Pace:
    id: str
    name: str
    miles: int
    pay: float
    health: int
    blurb: str


HUSTLES: tuple[Pace, ...] = (
    Pace("chill", "Chill", 60, 0.8, 2, "Slow progress, smaller paychecks, actual weekends."),
    Pace("steady", "Steady", 90, 1.0, -3, "A normal week. Whatever that means."),
    Pace("grind", "Grind", 120, 1.25, -8, "Fast and lucrative. Burnout is not a rumor."),
)
HUSTLE_BY_ID = {h.id: h for h in HUSTLES}


@dataclass(frozen=True)
class Budget:
    id: str
    name: str
    meals: int
    health: int
    blurb: str


BUDGETS: tuple[Budget, ...] = (
    Budget("frugal", "Frugal", 5, -3, "Rice, beans, and a slow decline in morale."),
    Budget("normal", "Normal", 7, 0, "Groceries with the occasional takeout."),
    Budget("treat", "Treat yourself", 10, 3, "Brunch is a lifestyle. Groceries go fast."),
)
BUDGET_BY_ID = {b.id: b for b in BUDGETS}

STARVATION_HEALTH = 15
WEEKLY_MEAL_MARKUP = 2  # corner-store price over the bulk store price
WEEKLY_BILLS = 100  # phone, utilities, streaming, the gym you don't go to
AILMENT_HEALTH = 12
REST_HEALTH = 10
CAR_REPAIR = 30
GIG_PAY = (150, 500)
GIG_ALL_NIGHTER_CHANCE = 0.2
JOB_HUNT_CHANCE = 0.3
JOB_HUNT_OUTFIT_BONUS = 0.25
GARNISH_RATE = 0.8

MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)  # fmt: skip

TRAIL_FLAVOR = (
    "The check-engine light is on, but it has been on for a while.",
    "Someone in the group chat sent a 47-second voice memo.",
    "You pass a billboard for a personal injury lawyer. It feels personal.",
    "The playlist has looped twice. Nobody says anything.",
    "A podcast ad tells you to invest in gold.",
    "You think about your inbox. You stop thinking about your inbox.",
    "The weather app says 40% chance of rain, which means nothing.",
    "Traffic. Just traffic.",
    "A stranger's Wi-Fi network is named 'FBI Surveillance Van 4'.",
    "You remember a thing you said in 2014.",
)

DEATH_CAUSES = ("burnout", "exhaustion", "sheer vibes", "a Tuesday")

RATINGS = (
    (3000, "Legend. You own a dishwasher and know how it works."),
    (1500, "Functional adult. Your plants are alive."),
    (500, "Adult, technically. The Wi-Fi works most days."),
    (0, "You made it. That counts."),
)
