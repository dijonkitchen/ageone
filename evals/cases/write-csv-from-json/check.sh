source "$EVALS_LIB/check.sh"
answer > "$EVAL_OUTPUT.csv"
node "$CASE_DIR/check.mjs" "$EVAL_OUTPUT.csv"
