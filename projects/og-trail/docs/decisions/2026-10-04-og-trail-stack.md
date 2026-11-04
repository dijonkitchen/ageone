# Decision Record 2026-10-04: og-trail Stack

## Status timeline

2026-10-04: Proposed by Claude, implementing [SPEC-2026-09-30-og-trail-rebuild](../../specs/SPEC-2026-09-30-og-trail-rebuild.md)

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for [the spec](../../specs/SPEC-2026-09-30-og-trail-rebuild.md) that runs one game engine behind a `view()`/`submit(value)` protocol, with a terminal frontend, a browser frontend over a small JSON HTTP API, save and resume with the random state, and random, rule-based, and LLM players driven headless by a batch command.

#### Non-functional

Installable in the pinned environment from the root `make`, with `make check` passing in CI.
No runtime dependencies for the engine; the LLM player stays optional and cheap.

### Nice to haves

#### Functional

Players and frontends share one protocol, so a new player or frontend needs no engine change.

#### Non-functional

A code base small enough for agents to change safely, with every event and landmark exercised by the tests automatically.

### Avoid out of scope runaway rabbit hole risks

#### Functional

A front-end framework or build step for one HTML page.

#### Non-functional

An LLM SDK or agent framework for one chat completion per turn.

## Decision

Started from the python project template (see [Project template](../../../../docs/decisions/2026-10-04-project-template.md)).
The old repo's stack still holds: Python 3.11+, uv, ruff, pytest, and the standard library's `http.server` for the browser API, now with mypy strict from the template.

- **Engine and content**: carried over from the old repo, since the spec asks for its content: `engine.py` (rules), `state.py` (`GameState`, `View`, `Choice`), and data in `content.py`, `events.py`, and `landmarks.py`.
- **Frontends**: `cli.py` for the terminal and `web.py` plus `static/index.html` for the browser, both over `Game.view()`/`Game.submit()`.
- **Players**: `players.py`, new here.
  A player sees only a `View` and answers with a string, as a frontend would.
  The LLM player reads its model by role from the root [`harness/models.json`](../../../../harness/models.json) (default `cheap`) and posts to OpenRouter with `urllib` and the config's routing settings, so it adds no dependency.
- **Batch**: `og-trail batch` runs a player over seeded games per profession and writes one NDJSON line per game (`player`, `seed`, `profession`, `outcome`, `score`, `weeks`, `tokens`, `cost`, `fallbacks`, and `model` for the LLM player).

### High-level C4(context/container/component/code) diagram

```text
terminal (cli.py) ─┐
browser (index.html → web.py JSON API) ─┼─> Game.view() / Game.submit() (engine.py) ─> content, events, landmarks
players (random, rules, llm) ─┘
llm player ─> harness/models.json role ─> OpenRouter chat completions
og-trail batch ─> players over seeded games ─> NDJSON lines ─> eval pages
```

### Choices and Tradeoffs/Risks

- The runner, not the player, answers setup (name, profession, default party), so batch results compare by profession and players spend no tokens on setup.
- The LLM player sends one stateless request per screen (screen, status, last five log lines), which keeps cost flat over a 25–40 week game at the price of no memory beyond the log.
- An invalid answer is shown back once; a second takes a fallback that moves the game on (`continue`, `leave`, `back`, else the first choice, `0`, or blank) and is counted, so a confused model cannot loop forever.
  A turn cap (`MAX_TURNS`) ends any game that still stalls as `timeout`.
- The rule-based player wins nearly every tech and nurse game and about 40% of barista games over seeds 0–19; random wins under half as often (tested per profession).

### Dependencies

None at runtime; ruff, mypy, and pytest for development.

### Interfaces

- `Game.view() -> View` and `Game.submit(value: str) -> View`, raising `InvalidInput` with the game unchanged.
- `Game.to_dict()` / `Game.from_dict()` for saves, including the RNG state.
- HTTP: `POST /api/games`, `GET /api/games/<id>`, `POST /api/games/<id>/input`.
- `Player.choose(view, error=None) -> str`, and `play_game(player, seed, profession) -> dict` for one NDJSON record.

## Key Results and retrospective feedback
