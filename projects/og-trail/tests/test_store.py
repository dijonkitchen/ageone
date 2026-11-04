import pytest

from og_trail.engine import InvalidInput


def test_store_lists_every_item_and_a_way_out(store_game):
    view = store_game.view()
    ids = {c.id for c in view.choices}
    assert {"buy:groceries", "buy:coffee", "buy:meds", "buy:parts", "buy:outfits", "leave"} <= ids
    assert view.status["money"] == 5000


def test_buying_asks_for_quantity_then_deducts_money(store_game):
    view = store_game.submit("buy:groceries")
    assert view.input_type == "number"
    view = store_game.submit("50")
    assert view.phase == "store"
    assert store_game.state.supplies["groceries"] == 50
    assert store_game.state.money == 5000 - 50 * 4


def test_cannot_overspend(store_game):
    store_game.submit("buy:parts")
    with pytest.raises(InvalidInput):
        store_game.submit("1000")
    assert store_game.state.money == 5000
    assert store_game.view().input_type == "number"


def test_non_numeric_quantity_is_rejected(store_game):
    store_game.submit("buy:parts")
    with pytest.raises(InvalidInput):
        store_game.submit("lots")


def test_zero_quantity_cancels_purchase(store_game):
    store_game.submit("buy:parts")
    view = store_game.submit("0")
    assert view.phase == "store"
    assert store_game.state.money == 5000


def test_leaving_store_starts_the_trail(store_game):
    view = store_game.submit("leave")
    assert view.phase == "travel"
    assert view.status["week"] == 1
    assert view.status["miles"] == 0
