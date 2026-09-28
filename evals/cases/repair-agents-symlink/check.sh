source "$CASE_DIR/../../lib/check.sh"
only_changed README.md AGENTS.md
[ "$(readlink AGENTS.md)" = README.md ] || fail "AGENTS.md is not a symlink to README.md"
[ "$(readlink CLAUDE.md)" = AGENTS.md ] || fail "CLAUDE.md is not a symlink to AGENTS.md"
grep -qF 'Run `make` before opening a pull request.' README.md || fail "the edit made to the copy was lost"
git show HEAD~1:README.md | while IFS= read -r line; do
  [ -z "$line" ] || grep -qxF -- "$line" README.md || fail "README.md lost a line: $line"
done
