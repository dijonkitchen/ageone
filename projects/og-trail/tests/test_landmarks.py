import pytest

from og_trail import landmarks
from og_trail.content import PROFESSION_BY_ID, WEEKLY_BILLS
from og_trail.engine import Game
from og_trail.state import TOTAL_MILES

from .conftest import on_the_trail

PAY = PROFESSION_BY_ID["tech"].weekly_pay


@pytest.fixture
def quiet() -> Game:
    game = on_the_trail()
    game.event_chance = 0.0
    return game


def arrive(game: Game, miles: int) -> None:
    game.state.landmarks_seen = [lm.miles for lm in landmarks.LANDMARKS if 0 < lm.miles < miles]
    game.state.miles = miles - 1
    game.state.hustle = "chill"
    game.submit("continue")


def test_landmarks_are_ordered_and_end_at_stability():
    miles = [lm.miles for lm in landmarks.LANDMARKS]
    assert miles == sorted(miles)
    assert miles[-1] == TOTAL_MILES
    assert len(set(miles)) == len(miles)


def test_status_names_the_next_landmark(quiet):
    status = quiet.view().status
    assert status["next_landmark"]["name"] == "First Paycheck Falls"
    assert status["next_landmark"]["miles"] == 200


def test_crossing_a_landmark_interrupts_travel_once(quiet):
    arrive(quiet, 200)
    view = quiet.view()
    assert view.phase == "landmark"
    assert "First Paycheck Falls" in view.title
    view = quiet.submit("continue")
    assert view.phase == "travel"
    assert 200 in quiet.state.landmarks_seen
    quiet.state.miles = 201
    quiet.submit("continue")
    assert quiet.view().phase == "travel"


def test_every_landmark_can_be_visited_and_left():
    for lm in landmarks.LANDMARKS[1:-1]:
        game = on_the_trail(seed=3)
        game.event_chance = 0.0
        arrive(game, lm.miles)
        view = game.view()
        assert view.phase == "landmark", lm.name
        view = game.submit(view.choices[0].id)
        if view.phase == "store":
            view = game.submit("leave")
        assert view.phase == "travel", lm.name


def test_landmark_takes_priority_over_events():
    game = on_the_trail()
    game.event_chance = 1.0
    arrive(game, 200)
    assert game.view().phase == "landmark"


def test_student_loans_paid_in_full(quiet):
    arrive(quiet, 400)
    money = quiet.state.money
    quiet.submit("pay")
    assert quiet.state.money == money - landmarks.LOAN_BALANCE
    assert quiet.state.loan_plan == "paid"


def test_student_loans_cannot_be_paid_when_broke(quiet):
    quiet.state.money = 100
    arrive(quiet, 400)
    assert "pay" not in {c.id for c in quiet.view().choices}


def test_income_based_repayment_costs_weekly(quiet):
    arrive(quiet, 400)
    quiet.submit("ibr")
    money = quiet.state.money
    quiet.submit("continue")
    assert quiet.state.money == money + round(PAY * 0.8) - WEEKLY_BILLS - landmarks.LOAN_WEEKLY


def test_ignoring_loans_sets_the_flag(quiet):
    arrive(quiet, 400)
    quiet.submit("ignore")
    assert quiet.state.loan_plan == "ignored"


def test_insurance_premiums_are_charged_weekly(quiet):
    arrive(quiet, 800)
    quiet.submit("gold")
    money = quiet.state.money
    quiet.submit("continue")
    assert quiet.state.money == money + round(PAY * 0.8) - WEEKLY_BILLS - landmarks.PREMIUMS["gold"]


def test_forts_reopen_the_store_with_inflation(quiet):
    arrive(quiet, 600)
    view = quiet.submit("shop")
    assert view.phase == "store"
    assert quiet.price("groceries") == 5
    view = quiet.submit("leave")
    assert view.phase == "travel"


def test_lease_renewal_signing_raises_rent(quiet):
    rent = quiet.state.rent
    arrive(quiet, 1800)
    quiet.submit("sign")
    assert quiet.state.rent == round(rent * 1.12)


def test_moving_is_expensive_but_cheaper_long_term(quiet):
    rent = quiet.state.rent
    arrive(quiet, 1800)
    money = quiet.state.money
    quiet.submit("move")
    assert quiet.state.money == money - landmarks.MOVING_COST
    assert quiet.state.rent == round(rent * 0.85)


def test_layoff_gulch_resume_makes_you_ready(quiet):
    arrive(quiet, 1400)
    quiet.submit("resume")
    assert quiet.state.resume_ready


def test_reunion_choice_heals_or_hurts(quiet):
    arrive(quiet, 1000)
    for p in quiet.state.party:
        p.health = 50
    quiet.submit("go")
    assert all(p.health == 60 for p in quiet.state.party)


def test_doomscroll_desert_deleting_apps_helps(quiet):
    arrive(quiet, 1600)
    for p in quiet.state.party:
        p.health = 50
    quiet.submit("delete")
    assert all(p.health == 55 for p in quiet.state.party)


def test_arriving_at_stability_wins_directly(quiet):
    arrive(quiet, TOTAL_MILES)
    assert quiet.view().phase == "won"
