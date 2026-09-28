sed -i -E "/SPEC-0004-eval/s/\| Open \|$/| In progress (eval-agent) |/; s/^updated_at: .*/updated_at: $EVAL_TODAY/" specs/PRIORITIES.md
