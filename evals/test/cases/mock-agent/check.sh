source "$CASE_DIR/../../../lib/check.sh"
[ "$(cat out.txt)" = ok ] || fail "out.txt is not ok"
