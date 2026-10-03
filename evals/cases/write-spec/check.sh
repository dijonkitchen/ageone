source "$EVALS_LIB/check.sh"
only_changed 'specs/.*'
# specs/SPEC-YYYY-MM-DD-slug.md, or specs/<project>/SPEC-YYYY-MM-DD-slug.md for a project folder, dated today.
f=$(changed | grep -E "^specs/([a-z0-9-]+/)?SPEC-$today-[^/]*\.md$" | sed 's#^specs/##')
[ "$(echo "$f" | grep -c .)" = 1 ] || fail "expected one new specs/SPEC-$today-*.md, got: $f"
echo "$f" | grep -qE "^([a-z0-9-]+/)?SPEC-$today-[a-z0-9]+(-[a-z0-9]+)*\.md$" || fail "bad file name: $f"
n=$(basename "$f" .md)
git cat-file -e "HEAD:specs/$f" 2>/dev/null && fail "$n already existed"
head -n1 "specs/$f" | grep -qE "^# $n: .+" || fail "bad title: $(head -n1 "specs/$f")"
for h in '## Functional requirements' '## Non-functional requirements' '## Definition of done'; do grep -qx "$h" "specs/$f" || fail "missing section: $h"; done
sed -n '/^## Definition of done/,$p' "specs/$f" | tail -n +2 | grep -q '[a-z]' || fail "empty definition of done"
grep -qi lint "specs/$f" || fail "spec is not about lint"
row=$(priority_rows | awk -F'\t' -v n="$n" '$1 == n')
[ -n "$row" ] || fail "no $n row in the priority table"
grep -qF "[$n]($f)" specs/PRIORITIES.md || fail "row does not link to $f"
[ "$(echo "$row" | cut -f2)" = SPEC-2026-09-26-make-setup ] || fail "dependency is not SPEC-2026-09-26-make-setup: $row"
[ "$(echo "$row" | cut -f3)" = 3 ] || fail "priority is not 3: $row"
echo "$row" | cut -f5 | grep -qxE 'Low|Medium|High' || fail "bad difficulty: $row"
[ "$(echo "$row" | cut -f6)" = Open ] || fail "status is not Open: $row"
table_sorted || fail "table is not sorted"
[ "$(updated_at)" = "$today" ] || fail "updated_at is $(updated_at), not $today"
