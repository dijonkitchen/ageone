head -n 13 "$CASE_DIR/fixture.md" > specs/PRIORITIES.md
grep -E '^\| \[SPEC-' "$CASE_DIR/fixture.md" |
  awk -F'|' '{ d = ($6 ~ /Low/) ? 1 : ($6 ~ /Medium/) ? 2 : 3; printf "%06d%d\t%s\n", $4, d, $0 }' |
  sort | cut -f2- >> specs/PRIORITIES.md
