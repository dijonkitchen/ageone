# Development and eval environment. Pinned by devenv.lock; update with `devenv update`.
# See docs/decisions/2026-09-26-reproducible-environment.md.
{ pkgs, ... }:

{
  packages = [
    pkgs.curl
    pkgs.git
    pkgs.jq
  ];

  # pi needs Node.js 22.19 or newer (SPEC-0002).
  languages.javascript = {
    enable = true;
    package = pkgs.nodejs_22;
    npm.enable = true;
  };

  enterTest = ''
    node --version
    node -e 'const [a, b] = process.versions.node.split(".").map(Number); process.exit(a > 22 || (a === 22 && b >= 19) ? 0 : 1)'
  '';
}
