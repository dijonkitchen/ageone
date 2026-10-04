# Development and eval environment. Pinned by devenv.lock; update with `devenv update`.
# See docs/decisions/2026-09-26-reproducible-environment.md.
{ pkgs, lib, ... }:

{
  packages = [
    pkgs.curl
    pkgs.git
    pkgs.jq
  ];

  # Node.js LTS: nixpkgs points `nodejs` at the current LTS line, so `make update` moves to the next LTS.
  # pi needs 22.19 or newer (SPEC-2026-09-26-vendor-neutral-ai-harness); enterTest checks it.
  languages.javascript = {
    enable = true;
    package = pkgs.nodejs;
    npm.enable = true;
    # Bun for TypeScript and plain JavaScript projects (projects/<slug>/ with a package.json).
    # See docs/decisions/2026-10-04-project-template.md.
    bun.enable = true;
  };

  # Python with uv for data and back-end projects (projects/<slug>/ with a pyproject.toml), such as the stock screener;
  # uv installs each project's locked packages into its .venv on `uv run` or `uv sync`.
  # See docs/decisions/2026-10-03-stock-screener-stack.md and docs/decisions/2026-10-04-project-template.md.
  languages.python = {
    enable = true;
    package = pkgs.python312;
    uv.enable = true;
  };
  # devenv points uv at one shared venv in .devenv/state; each project keeps its own .venv instead,
  # resolved from the folder uv runs in, so two projects' locked packages never overwrite each other.
  env.UV_PROJECT_ENVIRONMENT = lib.mkForce ".venv";

  enterTest = ''
    python --version
    uv --version
    uv run --no-project --python "$(command -v python)" python -c 'print("uv runs python")'
    bun --version
    bun -e 'console.log("bun runs typescript" as string)'
    node --version
    node -e 'const [a, b] = process.versions.node.split(".").map(Number); process.exit(a > 22 || (a === 22 && b >= 19) ? 0 : 1)'
  '';
}
