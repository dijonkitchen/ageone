import json
from pathlib import Path
from typing import Any

import pytest

from og_trail import cli
from og_trail.content import PROFESSIONS
from og_trail.players import (
    LLMPlayer,
    RandomPlayer,
    RulePlayer,
    parse_answer,
    play_game,
    prompt,
)
from og_trail.state import Choice, View

SEEDS = range(20)
RECORD_KEYS = {"player", "seed", "profession", "outcome", "score", "weeks", "tokens", "cost"}


def models_file(tmp_path: Path) -> Path:
    path = tmp_path / "models.json"
    path.write_text(
        json.dumps(
            {
                "roles": {"cheap": "openrouter/acme/tiny", "local": "ollama/llama"},
                "openRouter": {"routing": {"zdr": True, "data_collection": "deny"}},
            }
        )
    )
    return path


class Scripted:
    """A model stub: answers from a list, recording each request."""

    def __init__(self, answers: list[str]) -> None:
        self.answers = answers
        self.requests: list[dict[str, Any]] = []

    def __call__(self, url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        self.requests.append(body)
        answer = self.answers.pop(0) if self.answers else "continue"
        return {
            "choices": [{"message": {"content": answer}}],
            "usage": {"total_tokens": 10, "cost": 0.001},
        }


@pytest.mark.parametrize("profession", [p.id for p in PROFESSIONS])
def test_rules_reach_stability_more_often_than_random(profession: str) -> None:
    rules = [play_game(RulePlayer(), seed, profession) for seed in SEEDS]
    randoms = [play_game(RandomPlayer(seed), seed, profession) for seed in SEEDS]
    for record in rules + randoms:
        assert record["outcome"] in {"won", "died", "evicted"}

    def wins(records: list[dict[str, Any]]) -> int:
        return sum(r["outcome"] == "won" for r in records)

    assert wins(rules) > wins(randoms)


def test_same_seed_and_player_tell_the_same_story() -> None:
    assert play_game(RandomPlayer(7), 7, "nurse") == play_game(RandomPlayer(7), 7, "nurse")


def test_invalid_answers_are_shown_once_then_fall_back() -> None:
    class Stubborn:
        name = "stubborn"
        tokens = 0
        cost = 0.0

        def __init__(self) -> None:
            self.errors: list[str] = []

        def choose(self, view: View, error: str | None = None) -> str:
            if error is not None:
                self.errors.append(error)
            return "nope" if view.input_type == "choice" else "x"

    player = Stubborn()
    record = play_game(player, 3, "tech")
    assert record["outcome"] in {"won", "died", "evicted"}
    assert record["fallbacks"] > 0
    assert len(player.errors) == record["fallbacks"]


def test_llm_player_uses_the_role_and_routing(tmp_path: Path) -> None:
    post = Scripted([])
    player = LLMPlayer("cheap", models_path=models_file(tmp_path), post=post)
    view = View("travel", "Week 1", "Go?", "choice", [Choice("continue", "Continue")])
    assert player.choose(view) == "continue"
    body = post.requests[0]
    assert body["model"] == "acme/tiny"
    assert body["provider"] == {"zdr": True, "data_collection": "deny"}
    assert (player.tokens, player.cost) == (10, 0.001)


def test_llm_player_only_runs_openrouter_roles(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="openrouter"):
        LLMPlayer("local", models_path=models_file(tmp_path), post=Scripted([]))


def test_llm_game_counts_tokens_and_fallbacks(tmp_path: Path) -> None:
    post = Scripted(["leave", "banana", "still banana"])
    player = LLMPlayer("cheap", models_path=models_file(tmp_path), post=post)
    record = play_game(player, 1, "tech")
    assert record["fallbacks"] >= 1
    assert "was invalid" in post.requests[2]["messages"][1]["content"]
    assert record["tokens"] == 10 * len(post.requests)
    assert record["cost"] == pytest.approx(0.001 * len(post.requests))


def test_parse_answer_accepts_ids_numbers_and_quotes() -> None:
    view = View("t", "t", "", "choice", [Choice("a", "A"), Choice("b", "B")])
    assert parse_answer(view, "`b`\nbecause") == "b"
    assert parse_answer(view, "2") == "b"
    assert parse_answer(view, "") == ""


def test_prompt_lists_choice_ids_and_errors() -> None:
    view = View("event", "Wedding", "Go?", "choice", [Choice("go", "Go ($400)")])
    text = prompt(view, "'x' is not one of the choices.")
    assert "- go: Go ($400)" in text
    assert "'x' is not one of the choices." in text


def test_batch_writes_one_ndjson_line_per_game(tmp_path: Path) -> None:
    out = tmp_path / "results.ndjson"
    assert cli.main(["batch", "--player", "random", "--games", "2", "--out", str(out)]) == 0
    records = [json.loads(line) for line in out.read_text().splitlines()]
    assert len(records) == 2 * len(PROFESSIONS)
    assert all(RECORD_KEYS <= set(r) for r in records)
    assert {r["profession"] for r in records} == {p.id for p in PROFESSIONS}
