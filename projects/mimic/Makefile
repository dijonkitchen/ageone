# `make check` is what CI runs for this project (see the root .github/workflows/projects.yml).
# Run inside the root `make shell` environment, which provides Python, uv and Icarus Verilog.

.DEFAULT_GOAL := check
export UV_PROJECT_ENVIRONMENT := $(CURDIR)/.venv
.PHONY: check fix lint test rtl gl synth

check: lint test rtl ## Lint, typecheck, model tests, and RTL tests in lockstep with the model.

lint: ## Lint, format check, and typecheck the Python, lint the Verilog.
	uv sync --locked
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	$(if $(shell command -v verilator),verilator --lint-only -Wall -Wno-DECLFILENAME -Wno-UNUSEDSIGNAL --top-module tt_um_dijonkitchen_mimic src/*.v)

test: ## Assembler, model, and every scenario on the golden model.
	uv sync --locked
	uv run pytest

rtl: ## Every scenario on the RTL (Icarus Verilog), each output compared with the model every cycle.
	uv sync --locked
	. .venv/bin/activate && $(MAKE) -C test -s clean && $(MAKE) -C test -s
	uv run python -m cocotb_tools.check_results test/results.xml

gl: ## A subset of the scenarios on the gate-level netlist (test/Makefile picks it), in lockstep with the model.
	. .venv/bin/activate && $(MAKE) -C test -s clean && $(MAKE) -C test -s GATES=yes
	uv run python -m cocotb_tools.check_results test/results.xml

fix: ## Apply lint and format fixes.
	uv run ruff check --fix .
	uv run ruff format .
