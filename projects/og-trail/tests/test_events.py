import pytest

from og_trail import events
from og_trail.content import WEEKLY_BILLS
from og_trail.engine import Game

from .conftest import on_the_trail


@pytest.fixture
def quiet() -> Game:
    game = on_the_trail()
    game.event_chance = 0.0
    return game


def test_events_roll_after_a_week_on_the_trail():
    game = on_the_trail()
    game.event_chance = 1.0
    view = game.submit("continue")
    assert view.phase in {"travel", "event"}
    assert len(game.state.log) > 1


def test_no_events_when_chance_is_zero(quiet):
    quiet.submit("continue")
    assert quiet.state.log == ["You hit the road."]


def test_every_event_can_fire_and_resolve():
    for event in events.EVENTS:
        game = on_the_trail(seed=7)
        game.event_chance = 0.0
        game.state.miles = 500
        game.state.insurance = "bronze"
        game.state.loan_plan = "ignored"
        game.trigger_event(event.id)
        view = game.view()
        if view.phase == "event":
            assert view.choices, event.id
            game.submit(view.choices[0].id)
        assert game.view().phase in {"travel", "epitaph"}, event.id


def test_car_trouble_uses_a_spare_part(quiet):
    quiet.trigger_event("car_trouble")
    assert quiet.state.supplies["parts"] == 1
    assert quiet.state.car == 100


def test_car_trouble_without_parts_damages_car_and_costs_a_tow(quiet):
    quiet.state.supplies["parts"] = 0
    money = quiet.state.money
    quiet.trigger_event("car_trouble")
    assert quiet.state.car == 70
    assert quiet.state.money == money - 350


def test_a_cold_makes_someone_sick_and_bills_by_insurance(quiet):
    quiet.state.insurance = "none"
    money = quiet.state.money
    quiet.trigger_event("cold")
    assert sum(1 for p in quiet.state.party if p.ailment) == 1
    assert quiet.state.money == money - 600


def test_a_cold_is_free_on_a_gold_plan(quiet):
    quiet.state.insurance = "gold"
    money = quiet.state.money
    quiet.trigger_event("cold")
    assert quiet.state.money == money


def test_wedding_is_a_choice(quiet):
    view = quiet.trigger_event("wedding")
    assert view.phase == "event"
    assert {c.id for c in view.choices} == {"go", "decline"}
    money = quiet.state.money
    for p in quiet.state.party:
        p.health = 50
    view = quiet.submit("go")
    assert view.phase == "travel"
    assert quiet.state.money == money - 600
    assert all(p.health == 60 for p in quiet.state.party)


def test_declining_the_wedding_costs_morale(quiet):
    quiet.trigger_event("wedding")
    quiet.submit("decline")
    assert all(p.health == 95 for p in quiet.state.party)


def test_wedding_cannot_be_attended_when_broke(quiet):
    quiet.state.money = 100
    view = quiet.trigger_event("wedding")
    assert {c.id for c in view.choices} == {"decline"}


def test_layoff_stops_pay_until_rehired(quiet):
    quiet.trigger_event("layoff")
    assert not quiet.state.employed
    assert quiet.state.unemployed_weeks >= 3
    quiet.state.supplies["outfits"] = 0
    money = quiet.state.money
    quiet.rng.random = lambda: 0.99  # never lucky
    quiet.submit("continue")
    assert quiet.state.money == money - WEEKLY_BILLS


def test_resume_halves_the_layoff(quiet):
    quiet.state.resume_ready = True
    quiet.trigger_event("layoff")
    assert quiet.state.unemployed_weeks <= 3


def test_rent_hike_raises_rent(quiet):
    rent = quiet.state.rent
    quiet.trigger_event("rent_hike")
    assert quiet.state.rent > rent


def test_garnishment_only_when_loans_are_ignored(quiet):
    assert not events.EVENT_BY_ID["garnishment"].when(quiet)
    quiet.state.loan_plan = "ignored"
    assert events.EVENT_BY_ID["garnishment"].when(quiet)
    quiet.trigger_event("garnishment")
    assert quiet.state.garnished
    assert not events.EVENT_BY_ID["garnishment"].when(quiet)


def test_burnout_is_more_likely_when_grinding(quiet):
    burnout = events.EVENT_BY_ID["burnout"]
    steady = burnout.weight_for(quiet)
    quiet.state.hustle = "grind"
    assert burnout.weight_for(quiet) > steady


def test_event_choice_that_kills_the_leader_ends_the_game(quiet):
    quiet.state.leader.health = 2
    quiet.trigger_event("dentist")
    quiet.state.supplies["meds"] = 0
    quiet.submit("ignore")
    quiet.submit("continue")
    assert quiet.view().phase == "epitaph"


def test_unknown_event_is_an_error(quiet):
    with pytest.raises(KeyError):
        quiet.trigger_event("meteor")
