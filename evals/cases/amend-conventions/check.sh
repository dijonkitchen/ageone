source "$EVALS_LIB/check.sh"
f=docs/decisions/2026-09-26-conventions.md
only_changed "$f"
grep -qE "^$today: Amended by eval-agent" "$f" || fail "no '$today: Amended by eval-agent' status entry"
git show HEAD:"$f" | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}: ' | while IFS= read -r line; do
  grep -qxF -- "$line" "$f" || fail "status entry changed or removed: $line"
done
grep -q 'evals/cases' "$f" || fail "the decision itself does not mention evals/cases"
deleted=$(git diff HEAD --numstat -- "$f" | cut -f2)
[ "${deleted:-0}" -le 2 ] || fail "$deleted lines deleted: amend, don't rewrite"
