# Helpers for case graders (check.sh), which run in the sandbox after the harness finishes.
# The sandbox is a Git repo: HEAD is the starting state, so `git diff HEAD` shows what the model changed.
set -euo pipefail

fail() { echo "FAIL: $*"; exit 1; }
today="${EVAL_TODAY:-$(date -u +%F)}"

# Paths changed since the start (modified, added, deleted, untracked), one per line.
changed() { git add -A -N . && git diff HEAD --name-only; }

# Fail unless every changed path matches one of the given extended regexes.
only_changed() {
  local pattern
  pattern="^($(IFS='|'; echo "$*"))$"
  local extra
  extra=$(changed | grep -Ev "$pattern" || true)
  [ -z "$extra" ] || fail "unexpected changes: $(echo "$extra" | tr '\n' ' ')"
}

# Rows of the priority table as tab-separated fields: number, dependency, priority, description, difficulty, status.
priority_rows() {
  grep -E '^\| *\[SPEC-' "${1:-specs/PRIORITIES.md}" |
    sed -E 's/^\| *//; s/ *\| *$//; s/ *\| */\t/g; s/^\[(SPEC-[0-9]+)\]\([^)]*\)/\1/'
}

# The table is sorted by priority, then difficulty (Low, Medium, High).
table_sorted() {
  priority_rows "$@" | awk -F'\t' '
    { d = ($5 == "Low") ? 1 : ($5 == "Medium") ? 2 : ($5 == "High") ? 3 : 9
      key = sprintf("%06d%d", $3, d)
      if (NR > 1 && key < prev) { print "out of order at " $1; bad = 1 }
      prev = key }
    END { exit bad }'
}

updated_at() { sed -nE 's/^updated_at: *([0-9-]+).*/\1/p' "${1:-specs/PRIORITIES.md}"; }

# The model's final answer, for direct cases, with surrounding blank lines and a Markdown code fence removed.
answer() { sed -e '/^```/d' "$EVAL_OUTPUT" | sed -e '/./,$!d' | sed -e ':a' -e '/^\n*$/{$d;N;ba' -e '}'; }
