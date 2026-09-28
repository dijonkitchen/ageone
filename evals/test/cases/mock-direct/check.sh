source "$CASE_DIR/../../../lib/check.sh"
[ "$(answer)" = 42 ] || fail "expected 42, got $(answer)"
