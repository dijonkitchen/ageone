# roi

Screens stocks and options and evaluates strategies offline, in a ports-and-adapters shape where live data plugs in as an adapter, with a research assistant that writes cited summaries of a shortlist's filings and news; nothing places a live order.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [Spec](specs/SPEC-2026-09-30-roi-rebuild.md): what to build and the definition of done.
- [Stack decision](docs/decisions/2026-10-23-roi-stack.md): the toolchain, the shape, and why.
- [Acceptance criteria](docs/acceptance.md): the criteria tests cite by ID.

## Commands

Run from this folder, inside the root `make shell` environment.
- `make check`: lint, format check, typecheck, and tests; CI runs it whenever this folder changes.
- `make fix`: apply lint and format fixes.
- `uv run roi`: screen a sample universe and backtest it, offline.
- `uv run roi research`: cited summaries of a sample shortlist, by the `default` model role (`--role cheap` for another); needs `OPENROUTER_API_KEY`. `--prompt` prints the prompt without one.
- `uv sync --extra openbb`: install OpenBB for `OpenBBMarketData` live prices.
- From the repo root, `evals/run --harness direct --model default --case roi-cited-research`: the assistant's eval (needs `OPENROUTER_API_KEY`).

## Rules

- Commit the lockfile (`bun.lock` or `uv.lock`) with any dependency change.
- The core (everything outside `adapters/`) has no I/O and no dependencies; anything that reaches outside is an adapter behind a port, with an injectable fetcher so tests stay offline. Tests run with the network blocked.
- `PaperBroker` is the only broker. A live broker would be a deliberate, opt-in adapter under the same risk limits, and needs its own spec.
- No model IDs in code: the assistant takes a role from `harness/models.json`.
- Tag each test with the acceptance criteria it checks (`@pytest.mark.criteria("SCR-1")`); add new criteria to `docs/acceptance.md`.
- If the research prompt or sample changes, regenerate `evals/cases/roi-cited-research/case.json` (a test says when); its `prompt` is `uv run python -m roi.research --prompt`.
- Not investment advice: the assistant describes, and its checks reject anything that suggests an order.
