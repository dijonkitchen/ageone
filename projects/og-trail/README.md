# OG Trail

The Oregon Trail, but for modern life.
You leave your parents' driveway with a used car, a few friends, and 2,000 miles of rent, group chats, student loans, and check-engine lights between you and Stability (a modest apartment with a dishwasher).

Restarted from [dijonkitchen/og_trail](https://github.com/dijonkitchen/og_trail) per [SPEC-2026-09-30-og-trail-rebuild](specs/SPEC-2026-09-30-og-trail-rebuild.md).

## Play

```sh
uv run og-trail                         # terminal
uv run og-trail web                     # browser at http://127.0.0.1:8000
uv run og-trail --seed 42               # reproducible run
uv run og-trail --save game.json        # autosave every turn; resumes if present
```

In the terminal, type a choice's number or id; `quit` leaves.
The browser talks to the same engine over a small JSON API (`POST /api/games`, `GET /api/games/<id>`, `POST /api/games/<id>/input`).

## Agent players

`og-trail batch` plays seeded games headless and writes one NDJSON line per game:

```sh
uv run og-trail batch --player random --games 20
uv run og-trail batch --player rules --games 20 --out results.ndjson
OPENROUTER_API_KEY=... uv run og-trail batch --player llm --role cheap --games 3
```

Each line has `player`, `seed`, `profession`, `outcome` (`won`, `died`, `evicted`, or `timeout`), `score` (0 unless won), `weeks`, `tokens`, `cost` (USD as reported by OpenRouter), `fallbacks`, and `model` for the LLM player.

- **random** picks any valid-looking answer.
- **rules** stocks up, keeps a steady pace and normal budget, rests when hurt, fixes the car, and takes side gigs when cash is short.
- **llm** asks the model for a role in the root [`harness/models.json`](../../harness/models.json) (default `cheap`) through OpenRouter with its routing settings, one screen per request.

The runner fills in setup (name, profession, default party) so results compare by profession.
An invalid answer is shown back to the player once; a second invalid answer takes a fallback that moves the game on (`continue`, `leave`, `back`, else the first choice, `0`, or blank) and counts it in `fallbacks`.
