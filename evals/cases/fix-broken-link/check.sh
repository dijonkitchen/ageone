source "$EVALS_LIB/check.sh"
only_changed README.md
grep -oE '\]\([^)#]+' README.md | sed 's/^](//' | grep -vE '^[a-z]+:' | while read -r target; do
  [ -e "$target" ] || fail "README.md still links to missing $target"
done
grep -qF '(docs/decisions/2026-09-26-conventions.md)' README.md || fail "the conventions link does not point at docs/decisions/2026-09-26-conventions.md"
