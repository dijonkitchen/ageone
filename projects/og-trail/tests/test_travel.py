import pytest

from og_trail.content import PROFESSION_BY_ID, WEEKLY_BILLS
from og_trail.engine import Game
from og_trail.landmarks import LANDMARKS
from og_trail.state import TOTAL_MILES

from .conftest import on_the_trail

PAY = PROFESSION_BY_ID["tech"].weekly_pay
BILLS = WEEKLY_BILLS


@pytest.fixture
def quiet() -> Game:
    """A trail game with events off and landmarks pre-visited, for determinism."""
    game = on_the_trail()
    game.event_chance = 0.0
    game.state.landmarks_seen = [lm.miles for lm in LANDMARKS]
    return game


def test_continue_advances_a_week_and_some_miles(quiet):
    quiet.submit("continue")
    assert quiet.state.week == 2
    assert 70 <= quiet.state.miles <= 110  # steady pace is 90 give or take 15%


def test_steady_weeks_wear_you_down_a_little(quiet):
    quiet.submit("continue")
    assert all(p.health == 97 for p in quiet.state.party)


def test_grind_is_faster_and_tiring(quiet):
    quiet.submit("hustle")
    view = quiet.submit("grind")
    assert view.phase == "travel"
    quiet.submit("continue")
    assert quiet.state.miles >= 100
    assert all(p.health < 100 for p in quiet.state.party)


def test_chill_pace_pays_less(quiet):
    quiet.submit("hustle")
    quiet.submit("chill")
    before = quiet.state.money
    quiet.submit("continue")
    assert quiet.state.money == before + round(PAY * 0.8) - BILLS


def test_paycheck_arrives_and_bills_leave_every_week(quiet):
    before = quiet.state.money
    quiet.submit("continue")
    assert quiet.state.money == before + PAY - BILLS


def test_party_eats_by_budget(quiet):
    quiet.submit("continue")
    assert quiet.state.supplies["groceries"] == 100 - 5 * 7
    quiet.submit("budget")
    quiet.submit("frugal")
    quiet.submit("continue")
    assert quiet.state.supplies["groceries"] == 65 - 5 * 5


def test_groceries_are_bought_weekly_once_the_pantry_is_empty(quiet):
    quiet.state.supplies["groceries"] = 10
    before = quiet.state.money
    quiet.submit("continue")
    assert quiet.state.supplies["groceries"] == 0
    assert quiet.state.money == before + PAY - BILLS - 25 * quiet.weekly_meal_price()
    assert all(p.health == 97 for p in quiet.state.party)


def test_starving_costs_health_in_proportion(quiet):
    quiet.state.supplies["groceries"] = 0
    quiet.state.money = 0
    quiet.state.weekly_pay = 0
    quiet.submit("continue")
    assert all(p.health == 100 - 15 - 3 for p in quiet.state.party)
    assert any("hungry" in line for line in quiet.state.log)

    quiet.state.money = 0
    quiet.state.supplies["groceries"] = 35 // 2
    quiet.submit("continue")
    assert all(p.health == 82 - 8 - 3 for p in quiet.state.party)


def test_starving_to_death_is_called_hunger(quiet):
    quiet.state.supplies["groceries"] = 0
    quiet.state.money = 0
    quiet.state.weekly_pay = 0
    quiet.state.leader.health = 5
    view = quiet.submit("continue")
    assert view.phase == "epitaph"
    assert "died of hunger" in view.text


def test_rent_is_due_every_four_weeks(quiet):
    quiet.state.money = 0
    quiet.state.supplies["groceries"] = 999
    for _ in range(3):
        quiet.submit("continue")
    assert quiet.state.money == (PAY - BILLS) * 3
    quiet.submit("continue")
    assert quiet.state.week == 5
    assert quiet.state.money == (PAY - BILLS) * 4 - quiet.state.rent


def test_missing_rent_twice_gets_you_evicted(quiet):
    quiet.state.money = 0
    quiet.state.weekly_pay = 0
    quiet.state.supplies["groceries"] = 999
    for _ in range(4):
        quiet.submit("continue")
    assert quiet.state.missed_rent == 1
    assert quiet.view().phase == "travel"
    for _ in range(4):
        quiet.submit("continue")
    view = quiet.view()
    assert view.phase == "game_over"
    assert "parents" in view.text.lower()


def test_rest_heals_without_moving(quiet):
    for p in quiet.state.party:
        p.health = 50
    quiet.submit("rest")
    assert quiet.state.miles == 0
    assert quiet.state.week == 2
    assert all(p.health > 50 for p in quiet.state.party)


def test_side_gig_trades_coffee_for_money_once_a_week(quiet):
    before = quiet.state.money
    quiet.submit("gig")
    assert quiet.state.supplies["coffee"] == 4
    assert quiet.state.money > before
    assert "gig" not in {c.id for c in quiet.view().choices}
    quiet.submit("continue")
    assert "gig" in {c.id for c in quiet.view().choices}


def test_side_gig_needs_coffee(quiet):
    quiet.state.supplies["coffee"] = 0
    assert "gig" not in {c.id for c in quiet.view().choices}


def test_fix_car_uses_a_part(quiet):
    assert "fix" not in {c.id for c in quiet.view().choices}
    quiet.state.car = 40
    quiet.submit("fix")
    assert quiet.state.car == 70
    assert quiet.state.supplies["parts"] == 1


def test_broken_car_slows_you_down(quiet):
    quiet.state.car = 0
    quiet.submit("continue")
    assert quiet.state.miles <= 55


def test_status_screen_and_back(quiet):
    view = quiet.submit("status")
    assert view.phase == "status"
    assert "Priya" in view.text
    assert quiet.submit("back").phase == "travel"


def test_sick_traveler_is_cured_by_a_med_kit(quiet):
    quiet.state.party[1].ailment = "the flu"
    quiet.submit("continue")
    assert quiet.state.party[1].ailment is None
    assert quiet.state.supplies["meds"] == 2
    assert quiet.state.party[1].health == 100 - 12 - 3  # being sick still costs a week


def test_sick_traveler_without_meds_gets_worse(quiet):
    quiet.state.supplies["meds"] = 0
    quiet.state.party[1].ailment = "the flu"
    quiet.submit("continue")
    assert quiet.state.party[1].ailment == "the flu"
    assert quiet.state.party[1].health <= 100 - 12 - 3


def test_companion_death_is_reported_and_game_continues(quiet):
    quiet.state.party[2].health = 5
    quiet.state.party[2].ailment = "the flu"
    quiet.state.supplies["meds"] = 0
    quiet.submit("continue")
    assert not quiet.state.party[2].alive
    assert any("Marcus has died of the flu" in line for line in quiet.state.log)
    assert quiet.view().phase == "travel"


def test_leader_death_asks_for_an_epitaph(quiet):
    quiet.state.leader.health = 3
    quiet.state.supplies["groceries"] = 0
    quiet.submit("hustle")
    quiet.submit("grind")
    view = quiet.submit("continue")
    assert view.phase == "epitaph"
    assert view.input_type == "text"
    assert "died of" in view.text
    view = quiet.submit("Peperony and chease")
    assert view.phase == "game_over"
    assert "Peperony and chease" in view.text


def test_reaching_stability_wins_with_a_score(quiet):
    quiet.state.miles = TOTAL_MILES - 10
    view = quiet.submit("continue")
    assert view.phase == "won"
    assert quiet.score() > 0
    assert str(quiet.score()) in view.text


def test_harder_professions_multiply_score():
    tech = on_the_trail(profession="tech")
    barista = on_the_trail(profession="barista")
    for g in (tech, barista):
        g.state.money = 1000
        g.state.miles = TOTAL_MILES
    assert barista.score() == tech.score() * 3


def test_finished_games_offer_no_choices(quiet):
    quiet.state.miles = TOTAL_MILES
    quiet.submit("continue")
    assert quiet.view().input_type == "none"
