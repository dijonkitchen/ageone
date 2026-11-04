# `make check` is what CI runs for this project (see the root .github/workflows/projects.yml).
# It runs the checks of each toolchain the project uses: Bun when package.json exists, uv when pyproject.toml does.
# Run inside the root `make shell` environment, which provides Bun, Python, and uv.

.DEFAULT_GOAL := check
# Each project's own venv, even where the environment points uv at a shared one.
export UV_PROJECT_ENVIRONMENT := $(CURDIR)/.venv
.PHONY: check fix e2e

BUN := $(wildcard package.json)
UV := $(wildcard pyproject.toml)

check: ## Lint, format check, typecheck, and tests.
	$(if $(BUN)$(UV),,$(error no package.json or pyproject.toml: nothing to check))
ifneq ($(BUN),)
	bun install --frozen-lockfile
	bun run biome ci .
	bun run tsc --noEmit
	bun test src
endif
ifneq ($(UV),)
	uv sync --locked
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	uv run pytest
endif

fix: ## Apply lint and format fixes.
ifneq ($(BUN),)
	bun run biome check --write .
endif
ifneq ($(UV),)
	uv run ruff check --fix .
	uv run ruff format .
endif

e2e: ## Build the PWA and run the end-to-end tests in Chromium (CI installs it with `bunx playwright-core install chromium`).
	bun install --frozen-lockfile
	bun run e2e
