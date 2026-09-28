source "$EVALS_LIB/check.sh"
title=$(answer)
[ "$(echo "$title" | grep -c .)" = 1 ] || fail "expected one line, got: $title"
title=$(echo "$title" | sed -E 's/^`(.*)`$/\1/')
pattern=$(sed -nE "s/^ *pattern='(.*)'$/\1/p" "$REPO_ROOT/.github/workflows/pr-title.yml")
[[ "$title" =~ $pattern ]] || fail "does not match the PR title workflow: $title"
[[ "$title" =~ ^docs ]] || fail "a docs-only change should be type docs: $title"
