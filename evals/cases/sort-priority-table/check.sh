source "$EVALS_LIB/check.sh"
only_changed specs/PRIORITIES.md
table_sorted || fail "table is not sorted by priority, then difficulty"
[ "$(priority_rows | sort)" = "$(priority_rows <(git show HEAD:specs/PRIORITIES.md) | sort)" ] || fail "rows were added, removed, or edited"
