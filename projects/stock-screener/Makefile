# `make check` is what CI runs for this project (see the root .github/workflows/projects.yml).
# Started before the project template; it adopts the template's lint and tests, but not yet its
# format check (20 files predate it) or mypy. Run inside the root `make shell` environment.

.DEFAULT_GOAL := check
# Each project's own venv, even where the environment points uv at a shared one.
export UV_PROJECT_ENVIRONMENT := $(CURDIR)/.venv
.PHONY: check fix

check: ## Lint and tests on recorded fixtures, no network to the SEC.
	uv sync --locked
	uv run ruff check .
	uv run pytest

fix: ## Apply lint fixes.
	uv run ruff check --fix .
