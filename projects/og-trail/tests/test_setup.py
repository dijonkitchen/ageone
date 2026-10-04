import pytest

from og_trail.engine import Game, InvalidInput


def test_new_game_asks_for_name():
    view = Game(seed=1).view()
    assert view.phase == "setup_name"
    assert view.input_type == "text"
    assert view.choices == []


def test_setup_flow_reaches_store_with_profession_money():
    game = Game(seed=1)
    view = game.submit("Alex")
    assert view.phase == "setup_profession"
    assert view.input_type == "choice"
    assert {c.id for c in view.choices} == {"tech", "nurse", "barista"}

    view = game.submit("tech")
    assert view.phase == "setup_party"
    assert view.input_type == "text"

    view = game.submit("Priya, Marcus")
    assert view.phase == "store"
    assert game.state.money == 5000
    assert game.state.rent == 1400
    assert [p.name for p in game.state.party] == ["Alex", "Priya", "Marcus"]
    assert game.state.leader.name == "Alex"


def test_blank_inputs_use_defaults():
    game = Game(seed=1)
    game.submit("   ")
    game.submit("barista")
    game.submit("")
    assert game.state.leader.name == "Traveler"
    assert len(game.state.party) == 5
    assert game.state.money == 1500
    assert game.state.rent == 800


def test_too_many_companions_are_trimmed_to_four():
    game = Game(seed=1)
    game.submit("A")
    game.submit("nurse")
    game.submit("b, c, d, e, f, g")
    assert [p.name for p in game.state.party] == ["A", "b", "c", "d", "e"]


def test_invalid_choice_is_rejected_and_phase_unchanged():
    game = Game(seed=1)
    game.submit("Alex")
    with pytest.raises(InvalidInput):
        game.submit("astronaut")
    assert game.view().phase == "setup_profession"


def test_seed_makes_games_reproducible():
    a, b = Game(seed=42), Game(seed=42)
    for value in ("Alex", "nurse", ""):
        a.submit(value)
        b.submit(value)
    assert a.state.to_dict() == b.state.to_dict()
