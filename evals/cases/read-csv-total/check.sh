source "$CASE_DIR/../../lib/check.sh"
got=$(answer | tr -d ' *`')
[[ "$got" =~ ^17\.50*$ ]] || fail "expected 17.5, got: $got"
