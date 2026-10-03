f=docs/decisions/2026-09-26-conventions.md
last=$(grep -nE '^[0-9]{4}-[0-9]{2}-[0-9]{2}: ' "$f" | tail -n1 | cut -d: -f1)
sed -i "${last}a\\
\\
$EVAL_TODAY: Amended by eval-agent, at JC's request: eval case IDs are kebab-case." "$f"
sed -i 's/^- File names are kebab-case.$/&\n- Eval case IDs are kebab-case and match their folder name under `evals\/cases\/`./' "$f"
