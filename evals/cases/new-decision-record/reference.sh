f="docs/decisions/$EVAL_TODAY-ndjson-eval-results.md"
sed -e "s/^# Decision Record .*/# Decision Record $EVAL_TODAY: NDJSON Eval Results/" \
  -e "/^## Status timeline/,/^## Objective Context/c\\
## Status timeline\\
\\
$EVAL_TODAY: Proposed by eval-agent\\
\\
## Objective Context" \
  -e "s/^Simple markdown files like this one.$/Eval results are committed as NDJSON (one JSON object per line) under \`evals\/results\/\`./" \
  docs/decisions/2026-09-25-decision-records.md > "$f"
