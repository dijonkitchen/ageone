source "$EVALS_LIB/check.sh"
only_changed 'specs/.*'
last=$(git ls-tree --name-only HEAD specs/ | sed -nE 's/^specs\/SPEC-([0-9]{4}).*/\1/p' | sort -n | tail -n1)
n=$(printf 'SPEC-%04d' $((10#$last + 1)))
f=$(ls specs | grep -E "^$n-" || true)
[ -n "$f" ] || fail "no specs/$n-*.md"
echo "$f" | grep -qE "^$n-[a-z0-9]+(-[a-z0-9]+)*\.md$" || fail "bad file name: $f"
head -n1 "specs/$f" | grep -qE "^# $n: .+" || fail "bad title: $(head -n1 "specs/$f")"
for h in '## Functional requirements' '## Non-functional requirements' '## Definition of done'; do grep -qx "$h" "specs/$f" || fail "missing section: $h"; done
sed -n '/^## Definition of done/,$p' "specs/$f" | tail -n +2 | grep -q '[a-z]' || fail "empty definition of done"
grep -qi lint "specs/$f" || fail "spec is not about lint"
row=$(priority_rows | awk -F'\t' -v n="$n" '$1 == n')
[ -n "$row" ] || fail "no $n row in the priority table"
grep -qF "[$n]($f)" specs/PRIORITIES.md || fail "row does not link to $f"
[ "$(echo "$row" | cut -f2)" = SPEC-0003 ] || fail "dependency is not SPEC-0003: $row"
[ "$(echo "$row" | cut -f3)" = 3 ] || fail "priority is not 3: $row"
echo "$row" | cut -f5 | grep -qxE 'Low|Medium|High' || fail "bad difficulty: $row"
[ "$(echo "$row" | cut -f6)" = Open ] || fail "status is not Open: $row"
table_sorted || fail "table is not sorted"
[ "$(updated_at)" = "$today" ] || fail "updated_at is $(updated_at), not $today"
