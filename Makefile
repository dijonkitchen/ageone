# Entry points for people and agents. Each target is a thin wrapper; the environment itself is
# devenv.nix, pinned by devenv.lock. See specs/SPEC-0003-make-setup.md.

.DEFAULT_GOAL := help
.PHONY: help setup tools links shell check update

help: ## List targets.
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-8s %s\n", $$1, $$2}'

setup: tools links ## Check tools, repair entry-point symlinks, and build the pinned environment.
	devenv shell -- true
	@echo "Ready. Run 'make shell', or 'devenv hook' for auto-activation on cd."

tools: ## Fail with install steps if Nix or devenv is missing.
	@command -v nix >/dev/null || { echo "Nix is missing. Install: https://devenv.sh/getting-started/"; exit 1; }
	@command -v devenv >/dev/null || { echo "devenv is missing. Install: https://devenv.sh/getting-started/"; exit 1; }

links: ## Recreate AGENTS.md -> README.md and CLAUDE.md -> AGENTS.md; refuse if a copy has edits.
	@for pair in AGENTS.md:README.md CLAUDE.md:AGENTS.md; do \
		link=$${pair%%:*}; target=$${pair#*:}; \
		[ "$$(readlink $$link)" = "$$target" ] && continue; \
		if [ -e $$link ] && ! cmp -s $$link $$target; then \
			echo "$$link differs from $$target: move its edits into README.md, delete it, and rerun."; exit 1; \
		fi; \
		rm -f $$link; ln -s $$target $$link; echo "fixed $$link -> $$target"; \
	done

shell: ## Enter the pinned environment.
	devenv shell

check: links ## Run the environment's tests (devenv test).
	devenv test

update: ## Bump devenv.lock to the latest inputs; commit the diff only if 'make check' passes.
	devenv update
