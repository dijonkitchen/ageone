# Run `make`: it installs what is missing, builds the pinned environment, and checks it. Safe to rerun.
# The other targets are for debugging and maintenance.
# The environment itself is devenv.nix, pinned by devenv.lock. See specs/SPEC-2026-09-26-make-setup.md.

.DEFAULT_GOAL := all
.PHONY: all help setup tools links shell check update

# Find Nix and devenv right after installing them, before the shell is restarted.
# NIX_FLAGS covers a Nix installed earlier without flakes; new installs get --enable-flakes.
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
	@command -v nix >/dev/null || curl -sSfL $(NIX_INSTALLER) | sh -s -- install --enable-flakes $(if $(CI),--no-confirm)
	@# devenv comes from the nixpkgs commit pinned in devenv.lock (override with NIXPKGS=<flake ref>): other devenv versions rewrite the lock.
	@pkgs='$(NIXPKGS)'; [ -n "$$pkgs" ] || \
		pkgs=github:NixOS/nixpkgs/$$(nix $(NIX_FLAGS) eval --raw --impure --expr 'let l = builtins.fromJSON (builtins.readFile $(CURDIR)/devenv.lock); in l.nodes.$${l.nodes.$${l.root}.inputs.nixpkgs}.locked.rev') || exit 1; \
	command -v devenv >/dev/null || nix $(NIX_FLAGS) profile add $$pkgs#devenv || nix $(NIX_FLAGS) profile install $$pkgs#devenv || exit 1; \
	want=$$(nix $(NIX_FLAGS) eval --raw $$pkgs#devenv.version) || { echo "warning: could not read the pinned devenv version from $$pkgs"; exit 0; }; \
	have=$$(devenv version | cut -d' ' -f2); \
	[ "$$have" = "$$want" ] || echo "warning: devenv $$have is not the pinned $$want and may rewrite devenv.lock. Run 'nix profile remove devenv', then make."

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
