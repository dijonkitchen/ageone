# llm-from-scratch

A small GPT built step by step (tokenizer, transformer, training, generation, evaluation) to learn how language models work, trained on TinyStories on a laptop in under an hour.
The root [`AGENTS.md`](../../AGENTS.md) applies here too; this file adds only what is specific to this project.

## Read first

- [README](README.md): how to run each step, and the latest results.
- [Spec](specs/SPEC-2026-09-30-llm-from-scratch.md): what to build and the definition of done.
- [Stack decision](docs/decisions/2026-10-23-llm-from-scratch-stack.md): the toolchain and why.

## Commands

Run from this folder, inside the root `make shell` environment.

- `make check`: lint, format check, typecheck, and tests; CI runs it whenever this folder changes.
- `make fix`: apply lint and format fixes.
- `uv run python -m llm_from_scratch.<step> --help`: each step's explanation and flags.

## Rules

- Commit the lockfile (`uv.lock`) with any dependency change.
- Each module opens with a docstring that explains its step and why; keep it true when the code changes.
- Tests use tiny configs and the fixture stories, never the download, so `make check` stays fast and offline.
- Commit a run's `run.json`, `tokenizer.json`, and `compare.json`, never its `model.pt`; update the README's results from them.
