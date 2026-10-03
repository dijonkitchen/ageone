source "$EVALS_LIB/check.sh"
[ "$(cat out.txt)" = ok ] || fail "out.txt is not ok"
