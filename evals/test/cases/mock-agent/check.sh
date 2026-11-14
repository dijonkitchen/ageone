source "$EVALS_LIB/check.sh"
# The harness must leave nothing else behind, or every case graded with only_changed fails.
only_changed out.txt
[ "$(cat out.txt)" = ok ] || fail "out.txt is not ok"
