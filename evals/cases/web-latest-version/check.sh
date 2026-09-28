source "$CASE_DIR/../../lib/check.sh"
only_changed answer.md
[ -f answer.md ] || fail "no answer.md"
want=$(curl -sSf https://registry.npmjs.org/pi-web-access/latest | jq -r .version) || fail "grader could not reach the npm registry"
got=$(sed -nE 's/^version: *v?([0-9][^ ]*) *$/\1/p' answer.md)
[ "$got" = "$want" ] || fail "version '$got', latest is $want"
grep -qE '^source: *https?://[^ ]+' answer.md || fail "no source URL"
