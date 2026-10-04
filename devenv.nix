# Development and eval environment. Pinned by devenv.lock; update with `devenv update`.
# See docs/decisions/2026-09-26-reproducible-environment.md.
{ pkgs, ... }:

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
  };

  # Python for the stock screener (projects/stock-screener); uv installs its locked packages
  # into the project's .venv on `uv run` or `uv sync`. See docs/decisions/2026-10-03-stock-screener-stack.md.
  languages.python = {
    enable = true;
    package = pkgs.python312;
    uv.enable = true;
  };

  enterTest = ''
    python --version
    uv --version
    node --version
    node -e 'const [a, b] = process.versions.node.split(".").map(Number); process.exit(a > 22 || (a === 22 && b >= 19) ? 0 : 1)'
  '';
}
