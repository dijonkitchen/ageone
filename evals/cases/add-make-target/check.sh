source "$CASE_DIR/../../lib/check.sh"
only_changed Makefile 'README.md'
make -n evals 2>/dev/null | grep -qF 'evals/run --self-check' || fail "make -n evals does not run evals/run --self-check"
make help 2>/dev/null | grep -qE 'make evals' || fail "make help does not list evals"
grep -E '^\.PHONY:' Makefile | grep -qw evals || fail "evals is not .PHONY"
