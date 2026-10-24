"""Players that play over the view()/submit() protocol, and a runner for seeded games.

A player sees only what a frontend sees, a ``View``, and answers with one string.
The runner fills in setup (name, profession, party) so games compare by profession,
shows an invalid answer back to the player once, then takes a fallback and counts it.
"""

from __future__ import annotations

import json
import os
import random
import re
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from .engine import Game, InvalidInput
from .state import View

MAX_TURNS = 3000


class Player(Protocol):
    name: str
    tokens: int
    cost: float

    def choose(self, view: View, error: str | None = None) -> str:
        """Answer the view; ``error`` is set when the previous answer was invalid."""
        ...


# Fallback choices that move the game on, so a player that keeps failing still finishes.
MOVE_ON = ("continue", "leave", "back")


def fallback(view: View) -> str:
    if view.input_type == "choice":
        ids = [c.id for c in view.choices]
        return next((i for i in MOVE_ON if i in ids), ids[0])
    if view.input_type == "number":
        return "0"
    return ""


def outcome(game: Game) -> str:
    s = game.state
    if s.phase == "won":
        return "won"
    if s.phase not in {"game_over", "epitaph"}:
        return "timeout"
    return "evicted" if s.cause_of_death == "eviction" else "died"


def play_game(player: Player, seed: int, profession: str) -> dict[str, Any]:
    """Play one headless game and return its NDJSON record."""
    game = Game(seed=seed)
    game.submit(player.name)
    game.submit(profession)
    game.submit("")
    fallbacks = 0
    tokens, cost = player.tokens, player.cost
    for _ in range(MAX_TURNS):
        view = game.view()
        if view.input_type == "none":
            break
        try:
            game.submit(player.choose(view))
            continue
        except InvalidInput as exc:
            error = str(exc)
        try:
            game.submit(player.choose(view, error))
        except InvalidInput:
            fallbacks += 1
            game.submit(fallback(view))
    result = outcome(game)
    return {
        "player": player.name,
        "seed": seed,
        "profession": profession,
        "outcome": result,
        "score": game.score() if result == "won" else 0,
        "weeks": game.state.week,
        "tokens": player.tokens - tokens,
        "cost": round(player.cost - cost, 6),
        "fallbacks": fallbacks,
    }


# ------------------------------------------------------------------- random
class RandomPlayer:
    name = "random"

    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)
        self.tokens = 0
        self.cost = 0.0

    def choose(self, view: View, error: str | None = None) -> str:
        if view.input_type == "choice":
            return self.rng.choice(view.choices).id
        if view.input_type == "number":
            return str(self.rng.randint(0, 10))
        return ""


# --------------------------------------------------------------- rule-based
# Supplies to hold, in buying order; the player keeps a month's rent in cash.
STOCK = {"meds": 3, "parts": 2, "coffee": 4, "outfits": 1}
# Landmark and event answers, most preferred first; anything else takes the first choice.
PREFERRED = (
    "continue", "ibr", "bronze", "mute", "resume", "delete", "negotiate",
    "decline", "fix", "ignore", "post", "pay", "back",
)  # fmt: skip
PRICE = re.compile(r"^(?P<name>[^:\n]+): \$(?P<price>\d+) per", re.MULTILINE)


class RulePlayer:
    """A cautious player: stock up, keep a steady pace, rest when hurt, fix the car."""

    name = "rules"

    def __init__(self) -> None:
        self.tokens = 0
        self.cost = 0.0

    def choose(self, view: View, error: str | None = None) -> str:
        if error is not None:
            return fallback(view)
        handler: Callable[[View], str] | None = getattr(self, f"_{view.phase}", None)
        if handler is not None:
            return handler(view)
        if view.input_type == "text":
            return "Here lies someone who followed the rules."
        ids = [c.id for c in view.choices]
        return next((i for i in PREFERRED if i in ids), ids[0])

    def _reserve(self, view: View) -> int:
        return int(view.status["rent"])

    def _wanted(self, view: View) -> str | None:
        prices = {m["name"]: int(m["price"]) for m in PRICE.finditer(view.text)}
        money = int(view.status["money"])
        supplies = view.status["supplies"]
        for item, target in STOCK.items():
            price = next(p for n, p in prices.items() if _item_id(n) == item)
            if supplies[item] < target and money - price >= self._reserve(view):
                return item
        return None

    def _store(self, view: View) -> str:
        item = self._wanted(view)
        return f"buy:{item}" if item else "leave"

    def _store_qty(self, view: View) -> str:
        item = _item_id(view.title)
        price = int(re.search(r"\$(\d+) per", view.text).group(1))  # type: ignore[union-attr]
        spare = (int(view.status["money"]) - self._reserve(view)) // price
        need = STOCK[item] - int(view.status["supplies"][item])
        return str(max(0, min(need, spare)))

    def _travel(self, view: View) -> str:
        st = view.status
        ids = {c.id for c in view.choices}
        if "(now: Steady)" not in _label(view, "hustle"):
            return "hustle"
        if "(now: Normal)" not in _label(view, "budget"):
            return "budget"
        if min(p["health"] for p in st["party"] if p["alive"]) < 45:
            return "rest"
        if "fix" in ids and st["car"] < 70:
            return "fix"
        if "gig" in ids and st["money"] < 3 * st["rent"]:
            return "gig"
        return "continue"

    def _hustle(self, view: View) -> str:
        return "steady"

    def _budget(self, view: View) -> str:
        return "normal"


def _item_id(name: str) -> str:
    return {
        "Groceries": "groceries",
        "Coffee": "coffee",
        "Med kits": "meds",
        "Car parts": "parts",
        "Interview outfits": "outfits",
    }[name]


def _label(view: View, choice_id: str) -> str:
    return next((c.label for c in view.choices if c.id == choice_id), "")


# ---------------------------------------------------------------------- LLM
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SYSTEM = (
    "You are playing OG Trail, the Oregon Trail for modern life. "
    "Reach Stability at 2,000 miles with your party alive, rent paid, and money left. "
    "Each turn shows one screen. Reply with only your answer: the id of one choice, "
    "a whole number, or a short line of text, as the screen asks."
)
Post = Callable[[str, dict[str, Any], dict[str, str]], dict[str, Any]]


def find_models(start: Path | None = None) -> Path:
    """The repo's harness/models.json: OG_TRAIL_MODELS, else the nearest one up from here."""
    if env := os.environ.get("OG_TRAIL_MODELS"):
        return Path(env)
    for base in (start or Path.cwd(), Path(__file__)):
        for folder in (base, *base.parents):
            candidate = folder / "harness" / "models.json"
            if candidate.exists():
                return candidate
    raise FileNotFoundError("harness/models.json not found; set OG_TRAIL_MODELS")


def _post(url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        data: dict[str, Any] = json.load(resp)
        return data


def prompt(view: View, error: str | None = None) -> str:
    st = view.status
    lines = [f"# {view.title}", view.text]
    if st and view.phase not in {"setup_name", "setup_profession", "setup_party"}:
        party = ", ".join(f"{p['name']} {p['status']} ({p['health']})" for p in st["party"])
        lines += [
            "",
            (
                f"Week {st['week']}, {st['miles']}/{st['miles_total']} miles, ${st['money']:,}, "
                f"rent ${st['rent']:,} every 4 weeks, car {st['car']}%, "
                f"{'employed' if st['employed'] else 'job hunting'}."
            ),
            f"Supplies: {', '.join(f'{k} {v}' for k, v in st['supplies'].items())}.",
            f"Party: {party}.",
        ]
    if view.log:
        lines += ["", "Recently:", *(f"- {entry}" for entry in view.log[-5:])]
    if view.input_type == "choice":
        lines += ["", "Choices (reply with the id):"]
        lines += [f"- {c.id}: {c.label}" for c in view.choices]
    elif view.input_type == "number":
        lines += ["", "Reply with a whole number."]
    else:
        lines += ["", "Reply with a short line of text."]
    if error:
        lines += ["", f"Your last answer was invalid: {error} Try again."]
    return "\n".join(lines)


def parse_answer(view: View, text: str) -> str:
    answer = text.strip().splitlines()[0] if text.strip() else ""
    answer = answer.strip().strip("`'\"").strip()
    if view.input_type == "choice" and answer.isdigit():
        index = int(answer) - 1
        if 0 <= index < len(view.choices):
            return view.choices[index].id
    return answer


class LLMPlayer:
    """Asks a model chosen by role in harness/models.json, through OpenRouter."""

    def __init__(
        self,
        role: str = "cheap",
        models_path: Path | None = None,
        post: Post | None = None,
        api_key: str | None = None,
    ) -> None:
        config = json.loads((models_path or find_models()).read_text())
        model = config["roles"][role]
        provider, _, model_id = model.partition("/")
        if provider != "openrouter":
            raise ValueError(f"role {role} uses {model}; only openrouter/ models are supported")
        self.name = "llm"
        self.role = role
        self.model = model_id
        self.routing: dict[str, Any] = config.get("openRouter", {}).get("routing", {})
        self.post = post or _post
        self.api_key = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key and post is None:
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        self.tokens = 0
        self.cost = 0.0

    def choose(self, view: View, error: str | None = None) -> str:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt(view, error)},
            ],
            "provider": self.routing,
            "usage": {"include": True},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Title": "OG Trail",
        }
        data = self.post(OPENROUTER_URL, body, headers)
        usage = data.get("usage") or {}
        self.tokens += int(usage.get("total_tokens", 0))
        self.cost += float(usage.get("cost", 0.0))
        content = data["choices"][0]["message"].get("content") or ""
        return parse_answer(view, content)


def make_player(kind: str, seed: int = 0, role: str = "cheap") -> Player:
    if kind == "random":
        return RandomPlayer(seed)
    if kind == "rules":
        return RulePlayer()
    if kind == "llm":
        return LLMPlayer(role)
    raise ValueError(f"unknown player {kind}")
