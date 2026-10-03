source "$EVALS_LIB/check.sh"
only_changed specs/PRIORITIES.md
status=$(priority_rows | awk -F'\t' '$1 == "SPEC-0004" { print $6 }')
[ "$status" = "In progress (eval-agent)" ] || fail "SPEC-0004 status is '$status'"
for n in SPEC-0001 SPEC-0002 SPEC-0003; do
  [ "$(priority_rows | grep "^$n")" = "$(priority_rows <(git show HEAD:specs/PRIORITIES.md) | grep "^$n")" ] || fail "$n changed"
done
[ "$(updated_at)" = "$today" ] || fail "updated_at is $(updated_at), not $today"
