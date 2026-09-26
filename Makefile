# Run `make`: it installs what is missing, builds the pinned environment, and checks it. Safe to rerun.
# The other targets are for debugging and maintenance.
# The environment itself is devenv.nix, pinned by devenv.lock. See specs/SPEC-0003-make-setup.md.

.DEFAULT_GOAL := all
.PHONY: all help setup tools links shell check update

# Find Nix and devenv right after installing them, before the shell is restarted.
export PATH := /nix/var/nix/profiles/default/bin:$(HOME)/.nix-profile/bin:$(PATH)
NIX_INSTALLER ?= https://artifacts.nixos.org/nix-installer
NIX_FLAGS := --extra-experimental-features 'nix-command flakes'

all: setup check ## Default: install what is missing, build the environment, and run its tests.

help: ## List targets (everything but `make` is for debugging).
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-8s %s\n", $$1, $$2}'

setup: tools links ## Install what is missing, repair entry-point symlinks, and build the environment.
	devenv shell -- true
	@echo "Ready. Run 'make shell' to enter it."

tools: ## Install Nix (asks first, needs sudo) and devenv if missing.
	@command -v nix >/dev/null || curl -sSfL $(NIX_INSTALLER) | sh -s -- install $(if $(CI),--no-confirm)
	@command -v devenv >/dev/null || { nix $(NIX_FLAGS) profile add nixpkgs#devenv || nix $(NIX_FLAGS) profile install nixpkgs#devenv; }

links: ## Recreate AGENTS.md -> README.md and CLAUDE.md -> AGENTS.md; refuse if a copy has edits.
	@for pair in AGENTS.md:README.md CLAUDE.md:AGENTS.md; do \
		link=$${pair%%:*}; target=$${pair#*:}; \
		[ "$$(readlink $$link)" = "$$target" ] && continue; \
		if [ -e $$link ] && ! cmp -s $$link $$target; then \
			echo "$$link differs from $$target: move its edits into README.md, delete it, and rerun."; exit 1; \
		fi; \
		rm -f $$link; ln -s $$target $$link; echo "fixed $$link -> $$target"; \
	done

shell: setup ## Enter the pinned environment.
	devenv shell

check: setup ## Run the environment's tests.
	devenv test

update: tools ## Bump devenv.lock to the latest inputs; commit the diff only if 'make check' passes.
	devenv update
