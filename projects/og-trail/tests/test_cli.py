import json

from og_trail import cli
from og_trail.engine import Game
from og_trail.state import TOTAL_MILES

from .conftest import on_the_trail


def scripted(*answers: str):
    it = iter(answers)
    return lambda prompt: next(it)


def test_play_walks_setup_with_numbers_for_choices():
    out: list[str] = []
    game = Game(seed=1)
    game.event_chance = 0.0
    game.state.miles = TOTAL_MILES - 1  # so leaving the store wins immediately
    cli.play(game, read=scripted("Alex", "2", "Priya", "6", "1"), write=out.append)
    assert game.state.profession == "nurse"
    assert game.state.phase == "won"
    text = "\n".join(out)
    assert "Score" in text
    assert "Nurse" in text


def test_invalid_input_reprompts_instead_of_crashing():
    out: list[str] = []
    game = Game(seed=1)
    cli.play(
        game, read=scripted("Alex", "9", "tech", "", "1", "abc", "0", "6", "quit"), write=out.append
    )
    assert game.state.phase == "travel" or game.state.phase in {"landmark", "event"}
    assert any("not one of the choices" in line for line in out)
    assert any("whole number" in line for line in out)


def test_choice_ids_are_accepted_directly():
    game = on_the_trail()
    game.event_chance = 0.0
    out: list[str] = []
    cli.play(game, read=scripted("status", "back", "hustle", "grind", "quit"), write=out.append)
    assert game.state.hustle == "grind"


def test_eof_ends_the_session_cleanly():
    def read(prompt: str) -> str:
        raise EOFError

    out: list[str] = []
    cli.play(Game(seed=1), read=read, write=out.append)
    assert any("later" in line.lower() for line in out)


def test_render_shows_progress_and_party(trail_game):
    text = cli.render(trail_game.view(), fresh_log=["hello log"])
    assert "0/2000" in text
    assert "Alex" in text and "Theo" in text
    assert "hello log" in text
    assert "1)" in text


def test_autosave_writes_and_resumes(tmp_path):
    save = tmp_path / "game.json"
    game = on_the_trail(seed=9)
    game.event_chance = 0.0
    cli.play(game, read=scripted("continue", "quit"), write=lambda _: None, save_path=save)
    data = json.loads(save.read_text())
    assert data["week"] == 2

    resumed = cli.load_or_new(save_path=save, seed=None)
    assert resumed.state.week == 2
    assert resumed.state.leader.name == "Alex"


def test_main_runs_a_scripted_terminal_game(monkeypatch, capsys):
    answers = iter(["Alex", "1", "", "6", "quit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert cli.main(["--seed", "3"]) == 0
    assert "OG Trail" in capsys.readouterr().out
