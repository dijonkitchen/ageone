source "$EVALS_LIB/check.sh"
[ "$(answer)" = 42 ] || fail "expected 42, got $(answer)"
