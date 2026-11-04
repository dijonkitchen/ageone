"""The rules of OG Trail, exposed as a tiny screen/input protocol.

A ``Game`` always has exactly one current ``View``. A frontend draws the view,
collects one input of ``view.input_type``, and passes it to ``submit``. That is
the entire contract; the terminal and browser frontends both speak it.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from . import content, events, landmarks
from .state import MAX_PARTY, TOTAL_MILES, Choice, GameState, Person, View


class InvalidInput(ValueError):
    """The submitted value does not fit the current view."""


class Game:
    state: GameState
    rng: random.Random

    def __init__(self, seed: int | None = None, state: GameState | None = None) -> None:
        if state is not None:
            self.state = state
            self.rng = random.Random()
            if state.rng_state is not None:
                self.rng.setstate(_rng_state_from_json(state.rng_state))
            else:
                self.rng.seed(state.seed)
        else:
            if seed is None:
                seed = random.randrange(1 << 30)
            self.state = GameState(seed=seed)
            self.rng = random.Random(seed)

    # -------------------------------------------------------------- persistence
    def to_dict(self) -> dict[str, Any]:
        version, internal, gauss = self.rng.getstate()
        self.state.rng_state = [version, list(internal), gauss]
        return self.state.to_dict()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Game:
        return cls(state=GameState.from_dict(data))

    # ----------------------------------------------------------------- protocol
    def view(self) -> View:
        builder: Callable[[], View] = getattr(self, f"_view_{self.state.phase}")
        view = builder()
        view.status = self.status()
        view.log = list(self.state.log)
        return view

    def submit(self, value: str) -> View:
        view = self.view()
        value = value.strip()
        if view.input_type == "choice":
            if value not in {c.id for c in view.choices}:
                raise InvalidInput(f"'{value}' is not one of the choices.")
        elif view.input_type == "number" and not value.isdigit():
            raise InvalidInput("Please enter a whole number.")
        handler: Callable[[str], None] = getattr(self, f"_submit_{self.state.phase}")
        handler(value)
        return self.view()

    def status(self) -> dict[str, Any]:
        s = self.state
        return {
            "week": s.week,
            "miles": s.miles,
            "miles_total": TOTAL_MILES,
            "money": s.money,
            "hustle": s.hustle,
            "budget": s.budget,
            "car": s.car,
            "rent": s.rent,
            "employed": s.employed,
            "supplies": dict(s.supplies),
            "next_landmark": {
                "name": landmarks.next_landmark(s.miles).name,
                "miles": landmarks.next_landmark(s.miles).miles,
            },
            "party": [
                {"name": p.name, "health": p.health, "status": p.status, "alive": p.alive}
                for p in s.party
            ],
        }

    # -------------------------------------------------------------------- setup
    def _view_setup_name(self) -> View:
        return View(
            phase="setup_name",
            title="OG Trail",
            text=(
                "The Oregon Trail, but for modern life.\n\n"
                f"Ahead of you lie {TOTAL_MILES} miles of rent, group chats, and check-engine "
                "lights between your parents' driveway and something like Stability.\n\n"
                "What is your name?"
            ),
            input_type="text",
        )

    def _submit_setup_name(self, value: str) -> None:
        self.state.party = [Person(value or content.DEFAULT_LEADER)]
        self.state.phase = "setup_profession"

    def _view_setup_profession(self) -> View:
        lines = [
            f"{p.name}: starts with ${p.money:,}, earns ${p.weekly_pay}/week, "
            f"rent ${p.rent:,}/month. {p.blurb}"
            for p in content.PROFESSIONS
        ]
        return View(
            phase="setup_profession",
            title="Choose your profession",
            text=("Harder starts multiply your final score.\n\n" + "\n".join(lines)),
            input_type="choice",
            choices=[Choice(p.id, p.name) for p in content.PROFESSIONS],
        )

    def _submit_setup_profession(self, value: str) -> None:
        prof = content.PROFESSION_BY_ID[value]
        self.state.profession = prof.id
        self.state.money = prof.money
        self.state.weekly_pay = prof.weekly_pay
        self.state.rent = prof.rent
        self.state.phase = "setup_party"

    def _view_setup_party(self) -> View:
        return View(
            phase="setup_party",
            title="Your people",
            text=(
                f"Up to {MAX_PARTY - 1} friends, roommates, or partners are coming with you.\n"
                "Enter their names separated by commas, or leave blank for defaults."
            ),
            input_type="text",
        )

    def _submit_setup_party(self, value: str) -> None:
        names = [n.strip() for n in value.split(",") if n.strip()] or list(
            content.DEFAULT_COMPANIONS
        )
        self.state.party += [Person(n) for n in names[: MAX_PARTY - 1]]
        self.state.phase = "store"

    # -------------------------------------------------------------------- store
    def price(self, item_id: str) -> int:
        return round(content.ITEM_BY_ID[item_id].price * self.state.price_mult)

    def _view_store(self) -> View:
        lines = [
            f"{item.name}: ${self.price(item.id)} per {item.unit[:-1]}. {item.blurb}"
            for item in content.ITEMS
        ]
        return View(
            phase="store",
            title="Big Box Store",
            text=(
                "Fluorescent lights. A sample station. Everything you might need.\n\n"
                + "\n".join(lines)
            ),
            input_type="choice",
            choices=[Choice(f"buy:{i.id}", f"Buy {i.name.lower()}") for i in content.ITEMS]
            + [Choice("leave", "Leave the store")],
        )

    def _submit_store(self, value: str) -> None:
        if value == "leave":
            self.state.phase = "travel"
            self.state.say("You hit the road.")
            return
        self.state.pending_item = value.split(":", 1)[1]
        self.state.phase = "store_qty"

    def _view_store_qty(self) -> View:
        item = content.ITEM_BY_ID[self.state.pending_item or ""]
        price = self.price(item.id)
        affordable = self.state.money // price
        return View(
            phase="store_qty",
            title=item.name,
            text=(
                f"${price} per {item.unit[:-1]}. You can afford {affordable}. "
                f"How many {item.unit}? (0 to cancel)"
            ),
            input_type="number",
        )

    def _submit_store_qty(self, value: str) -> None:
        item_id = self.state.pending_item or ""
        qty = int(value)
        cost = qty * self.price(item_id)
        if cost > self.state.money:
            raise InvalidInput(f"That costs ${cost:,} and you have ${self.state.money:,}.")
        self.state.money -= cost
        self.state.supplies[item_id] += qty
        self.state.pending_item = None
        self.state.phase = "store"

    # ------------------------------------------------------------------- travel
    event_chance = events.DEFAULT_EVENT_CHANCE

    @property
    def hustle(self) -> content.Pace:
        return content.HUSTLE_BY_ID[self.state.hustle]

    @property
    def budget(self) -> content.Budget:
        return content.BUDGET_BY_ID[self.state.budget]

    def month(self) -> str:
        return content.MONTHS[((self.state.week - 1) // 4) % 12]

    def _view_travel(self) -> View:
        s = self.state
        flavor = content.TRAIL_FLAVOR[(s.week + s.seed) % len(content.TRAIL_FLAVOR)]
        choices = [
            Choice("continue", "Continue on the trail"),
            Choice("hustle", f"Change hustle (now: {self.hustle.name})"),
            Choice("budget", f"Change budget (now: {self.budget.name})"),
            Choice("rest", "Take a mental health week"),
        ]
        if s.supplies["coffee"] > 0 and not s.gigged_this_week:
            choices.append(Choice("gig", "Pick up a side gig (uses 1 coffee)"))
        if s.supplies["parts"] > 0 and s.car < 100:
            choices.append(Choice("fix", "Fix the car (uses 1 part)"))
        choices.append(Choice("status", "Check supplies and health"))
        return View(
            phase="travel",
            title=f"Week {s.week}, {self.month()}",
            text=f"{flavor}\n\n{s.miles} of {TOTAL_MILES} miles toward Stability.",
            input_type="choice",
            choices=choices,
        )

    def _submit_travel(self, value: str) -> None:
        s = self.state
        if value == "continue":
            self._tick(travel=True)
        elif value == "rest":
            for p in s.living:
                p.health = min(100, p.health + content.REST_HEALTH)
            s.say("You took the week off. You watched a whole show. You feel human.")
            self._tick(travel=False, pay_scale=0.5)
        elif value == "gig":
            self._side_gig()
        elif value == "fix":
            s.supplies["parts"] -= 1
            s.car = min(100, s.car + content.CAR_REPAIR)
            s.say(f"You swapped in a part. The car is at {s.car}%.")
        else:
            s.phase = value

    def _side_gig(self) -> None:
        s = self.state
        s.supplies["coffee"] -= 1
        s.gigged_this_week = True
        pay = self.rng.randint(*content.GIG_PAY)
        s.money += pay
        s.say(f"You took a side gig and made ${pay}.")
        if self.rng.random() < content.GIG_ALL_NIGHTER_CHANCE:
            s.leader.health = max(1, s.leader.health - 8)
            s.say("It took an all-nighter. You feel it.")

    def _view_hustle(self) -> View:
        lines = [f"{h.name}: {h.blurb}" for h in content.HUSTLES]
        return View(
            phase="hustle",
            title="How hard are you working?",
            text="\n".join(lines),
            input_type="choice",
            choices=[Choice(h.id, h.name) for h in content.HUSTLES],
        )

    def _submit_hustle(self, value: str) -> None:
        self.state.hustle = value
        self.state.phase = "travel"

    def _view_budget(self) -> View:
        lines = [f"{b.name}: {b.blurb}" for b in content.BUDGETS]
        return View(
            phase="budget",
            title="How are you spending?",
            text="\n".join(lines),
            input_type="choice",
            choices=[Choice(b.id, b.name) for b in content.BUDGETS],
        )

    def _submit_budget(self, value: str) -> None:
        self.state.budget = value
        self.state.phase = "travel"

    def _view_status(self) -> View:
        s = self.state
        people = [f"{p.name}: {p.status} ({p.health})" for p in s.party]
        supplies = [
            f"{content.ITEM_BY_ID[k].name}: {v} {content.ITEM_BY_ID[k].unit}"
            for k, v in s.supplies.items()
        ]
        job = "employed" if s.employed else f"between jobs ({s.unemployed_weeks} weeks)"
        return View(
            phase="status",
            title="Supplies and health",
            text=(
                "\n".join(people)
                + "\n\n"
                + "\n".join(supplies)
                + f"\n\nMoney: ${s.money:,}\nRent: ${s.rent:,} every 4 weeks"
                + f"\nCar: {s.car}%\nWork: {job}"
            ),
            input_type="choice",
            choices=[Choice("back", "Back to the trail")],
        )

    def _submit_status(self, value: str) -> None:
        self.state.phase = "travel"

    # ---------------------------------------------------------------- the week
    def _tick(self, travel: bool, pay_scale: float = 1.0) -> None:
        s = self.state
        s.week += 1
        s.gigged_this_week = False
        if travel:
            self._move()
        self._earn(pay_scale)
        self._bills()
        self._eat()
        self._heal_and_ail()
        self._pay_rent()
        self._bury_the_dead()
        if s.phase != "travel":
            return
        if s.miles >= TOTAL_MILES:
            s.miles = TOTAL_MILES
            s.phase = "won"
            return
        if self._arrive_somewhere():
            return
        if self.rng.random() < self.event_chance:
            self._roll_event()

    def _bills(self) -> None:
        s = self.state
        due = content.WEEKLY_BILLS + landmarks.PREMIUMS.get(s.insurance or "", 0)
        if s.loan_plan == "ibr":
            due += landmarks.LOAN_WEEKLY
        s.money = max(0, s.money - due)

    # ---------------------------------------------------------------- landmarks
    def _arrive_somewhere(self) -> bool:
        s = self.state
        for lm in landmarks.LANDMARKS[1:-1]:
            if s.miles >= lm.miles and lm.miles not in s.landmarks_seen:
                s.landmarks_seen.append(lm.miles)
                s.pending_landmark = lm.miles
                s.price_mult = max(s.price_mult, lm.price_mult)
                s.phase = "landmark"
                s.say(f"You reached {lm.name}.")
                return True
        return False

    def _view_landmark(self) -> View:
        lm = landmarks.LANDMARK_BY_MILES[self.state.pending_landmark or 0]
        return View(
            phase="landmark",
            title=f"{lm.name} ({lm.miles} miles)",
            text=lm.text,
            input_type="choice",
            choices=[Choice(o.id, o.label) for o in lm.choices_for(self)],
        )

    def _submit_landmark(self, value: str) -> None:
        s = self.state
        lm = landmarks.LANDMARK_BY_MILES[s.pending_landmark or 0]
        option = next(o for o in lm.options if o.id == value)
        s.pending_landmark = None
        s.phase = "travel"
        option.apply(self)
        self._bury_the_dead()

    # ------------------------------------------------------------------- events
    def _roll_event(self) -> None:
        weights = [e.weight_for(self) for e in events.EVENTS]
        if not any(weights):
            return
        event = self.rng.choices(events.EVENTS, weights=weights)[0]
        self.trigger_event(event.id)

    def trigger_event(self, event_id: str) -> View:
        """Fire a specific event now. Used by the roll, tests, and debugging."""
        event = events.EVENT_BY_ID[event_id]
        s = self.state
        s.pending_target = event.pick(self)
        if event.options:
            s.pending_event = event.id
            s.phase = "event"
        elif event.apply is not None:
            event.apply(self)
            self._bury_the_dead()
        return self.view()

    def _view_event(self) -> View:
        event = events.EVENT_BY_ID[self.state.pending_event or ""]
        return View(
            phase="event",
            title=event.title,
            text=event.render(self),
            input_type="choice",
            choices=[Choice(o.id, o.label) for o in event.options if o.when(self)],
        )

    def _submit_event(self, value: str) -> None:
        s = self.state
        event = events.EVENT_BY_ID[s.pending_event or ""]
        option = next(o for o in event.options if o.id == value)
        s.pending_event = None
        s.pending_target = None
        s.phase = "travel"
        option.apply(self)
        self._bury_the_dead()

    def _move(self) -> None:
        s = self.state
        car_factor = 0.5 + 0.5 * s.car / 100
        gain = round(self.hustle.miles * car_factor * self.rng.uniform(0.85, 1.15))
        s.miles += gain

    def _earn(self, scale: float) -> None:
        s = self.state
        if s.employed:
            pay = self.hustle.pay * s.weekly_pay * scale
            if s.garnished:
                pay *= content.GARNISH_RATE
            s.money += round(pay)
            return
        s.unemployed_weeks -= 1
        chance = content.JOB_HUNT_CHANCE
        if s.supplies["outfits"] > 0:
            s.supplies["outfits"] -= 1
            chance += content.JOB_HUNT_OUTFIT_BONUS
        if s.unemployed_weeks <= 0 or self.rng.random() < chance:
            s.unemployed_weeks = 0
            s.say("You landed a new job. The onboarding videos are 40 minutes long.")
        else:
            s.say("Still job hunting. A recruiter said they would 'circle back'.")

    def weekly_meal_price(self) -> int:
        return self.price("groceries") + content.WEEKLY_MEAL_MARKUP

    def _eat(self) -> None:
        s = self.state
        needed = self.budget.meals * len(s.living)
        from_pantry = min(s.supplies["groceries"], needed)
        s.supplies["groceries"] -= from_pantry
        to_buy = needed - from_pantry
        price = self.weekly_meal_price()
        bought = min(to_buy, s.money // price)
        s.money -= bought * price
        short = to_buy - bought
        s.starving = short > 0
        if not s.starving:
            return
        hit = round(content.STARVATION_HEALTH * short / needed)
        s.say("You could not afford enough groceries. Everyone is hungry and pretending not to be.")
        for p in s.living:
            p.health -= hit

    def _heal_and_ail(self) -> None:
        s = self.state
        delta = self.hustle.health + self.budget.health
        for p in s.living:
            if p.ailment:
                p.health -= content.AILMENT_HEALTH
                if s.supplies["meds"] > 0:
                    s.supplies["meds"] -= 1
                    s.say(f"You used a med kit. {p.name} is over {p.ailment}.")
                    p.ailment = None
            p.health = min(100, p.health + delta)

    def _pay_rent(self) -> None:
        s = self.state
        if s.week == 1 or (s.week - 1) % 4 != 0:
            return
        owed = s.rent * (s.missed_rent + 1)
        if s.money >= owed:
            s.money -= owed
            late = " (including what you owed)" if s.missed_rent else ""
            s.missed_rent = 0
            s.say(f"Rent day. You paid ${owed:,}{late}.")
            return
        s.missed_rent += 1
        if s.missed_rent >= 2:
            s.cause_of_death = "eviction"
            s.phase = "game_over"
            s.say("Rent day. You could not pay. Again.")
            return
        s.say(f"Rent day. You could not cover ${owed:,}. The landlord 'understands'. For now.")

    def _bury_the_dead(self) -> None:
        s = self.state
        for p in s.living:
            if p.health > 0:
                continue
            p.alive = False
            p.health = 0
            if p.ailment:
                cause = p.ailment
            elif s.starving:
                cause = "hunger"
            elif s.hustle == "grind":
                cause = "burnout"
            else:
                cause = self.rng.choice(content.DEATH_CAUSES)
            if p is s.leader:
                s.cause_of_death = cause
                s.phase = "epitaph"
            s.say(f"{p.name} has died of {cause}.")

    # ------------------------------------------------------------------ endings
    def _view_epitaph(self) -> View:
        return View(
            phase="epitaph",
            title="You have died",
            text=(
                f"You have died of {self.state.cause_of_death}.\n\n"
                "The group chat will be quiet for a while.\n\n"
                "What should your tombstone say?"
            ),
            input_type="text",
        )

    def _submit_epitaph(self, value: str) -> None:
        self.state.epitaph = value or "Here lies a person who tried."
        self.state.phase = "game_over"

    def _view_game_over(self) -> View:
        s = self.state
        if s.cause_of_death == "eviction":
            text = (
                "You have been evicted.\n\n"
                "You have moved back in with your parents. "
                "Your childhood bedroom is now a home gym."
            )
        else:
            text = (
                f"Here lies {s.leader.name}.\n"
                f"Died of {s.cause_of_death} in week {s.week}.\n\n"
                f'"{s.epitaph}"'
            )
        return View(phase="game_over", title="Game over", text=text, input_type="none")

    def _submit_game_over(self, value: str) -> None:
        raise InvalidInput("The game is over.")

    def score(self) -> int:
        s = self.state
        prof = content.PROFESSION_BY_ID[s.profession or "tech"]
        supplies_value = sum(content.ITEM_BY_ID[k].price * v for k, v in s.supplies.items())
        base = (
            s.money // 10
            + len(s.living) * 100
            + sum(p.health for p in s.living) // 2
            + supplies_value // 10
            + s.car // 2
        )
        return max(0, base) * prof.multiplier

    def _view_won(self) -> View:
        s = self.state
        score = self.score()
        rating = next(text for floor, text in content.RATINGS if score >= floor)
        survivors = ", ".join(p.name for p in s.living)
        return View(
            phase="won",
            title="Stability",
            text=(
                f"After {s.week} weeks you have reached Stability: a modest apartment "
                "with a dishwasher and a lease you can afford.\n\n"
                f"Arrived: {survivors}.\n"
                f"Money left: ${s.money:,}.\n\n"
                f"Score: {score}\n{rating}"
            ),
            input_type="none",
        )

    def _submit_won(self, value: str) -> None:
        raise InvalidInput("The game is over.")


def _rng_state_from_json(data: list[Any]) -> tuple[Any, ...]:
    version, internal, gauss = data
    return (version, tuple(internal), gauss)
