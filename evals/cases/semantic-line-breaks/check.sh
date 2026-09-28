source "$CASE_DIR/../../lib/check.sh"
f=docs/decisions/2026-09-20-cache-policy.md
only_changed "$f"
words() { tr -s ' \n' '  ' < "$1"; }
[ "$(words "$f")" = "$(words "$CASE_DIR/fixture.md")" ] || fail "wording changed"
# Paragraphs: blank-line-separated blocks must be unchanged once each is joined into one line.
paras() { awk 'BEGIN { RS = "" } { gsub(/\n/, " "); print }' "$1"; }
[ "$(paras "$f")" = "$(paras "$CASE_DIR/fixture.md")" ] || fail "paragraphs were merged or split"
bad=$(awk '/^```/ { code = !code; next } !code && /[.!?] +[A-Za-z]/' "$f")
[ -z "$bad" ] || fail "a line still holds more than one sentence: $bad"
grep -qxF 'keep this line. It is code.' "$f" || fail "the code block was reflowed"
