source "$CASE_DIR/../../lib/check.sh"
only_changed 'docs/decisions/.*' 'README.md'
new=$(git add -A -N . && git diff HEAD --name-only --diff-filter=A -- docs/decisions)
[ "$(echo "$new" | grep -c .)" = 1 ] || fail "expected one new decision record, got: $new"
echo "$new" | grep -qE "^docs/decisions/$today-[a-z0-9]+(-[a-z0-9]+)*\.md$" || fail "bad file name: $new"
head -n1 "$new" | grep -qE "^# Decision Record $today: .+" || fail "bad title: $(head -n1 "$new")"
for h in '## Status timeline' '## Objective Context' '## Decision'; do grep -qx "$h" "$new" || fail "missing section: $h"; done
grep -qE "^$today: Proposed by eval-agent" "$new" || fail "no '$today: Proposed by eval-agent' status entry"
grep -qi ndjson "$new" || fail "does not mention NDJSON"
git diff HEAD --quiet -- $(git ls-tree --name-only HEAD docs/decisions/) || fail "an existing decision record was edited"
