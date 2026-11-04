import pytest

from og_trail.engine import Game


def new_game(seed: int = 1, profession: str = "tech") -> Game:
    """A game advanced through setup to the opening store."""
    game = Game(seed=seed)
    game.submit("Alex")
    game.submit(profession)
    game.submit("Priya, Marcus, Jules, Theo")
    return game


def on_the_trail(seed: int = 1, profession: str = "tech") -> Game:
    """A game that has left the opening store with a sensible kit."""
    game = new_game(seed, profession)
    for item, qty in (("groceries", 100), ("coffee", 5), ("meds", 3), ("parts", 2), ("outfits", 2)):
        game.submit(f"buy:{item}")
        game.submit(str(qty))
    game.submit("leave")
    return game


@pytest.fixture
def store_game() -> Game:
    return new_game()


@pytest.fixture
def trail_game() -> Game:
    return on_the_trail()
