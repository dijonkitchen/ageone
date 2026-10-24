import json

from og_trail.engine import Game

from .conftest import on_the_trail


def test_round_trip_preserves_state_and_randomness():
    original = on_the_trail(seed=5)
    original.submit("continue")
    payload = json.dumps(original.to_dict())
    restored = Game.from_dict(json.loads(payload))

    assert restored.view().to_dict() == original.view().to_dict()
    for _ in range(6):
        for game in (original, restored):
            view = game.view()
            if view.input_type == "choice":
                game.submit(view.choices[0].id)
            elif view.input_type == "text":
                game.submit("x")
            else:
                break
    assert restored.state.to_dict() == original.state.to_dict()
    assert restored.rng.random() == original.rng.random()


def test_to_dict_is_json_serializable_at_every_phase():
    game = Game(seed=2)
    json.dumps(game.to_dict())
    game.submit("Alex")
    json.dumps(game.to_dict())
    game.submit("nurse")
    game.submit("")
    json.dumps(game.to_dict())
