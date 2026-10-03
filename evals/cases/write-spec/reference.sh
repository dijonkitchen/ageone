n=$(find specs -name 'SPEC-*.md' | sed -nE 's#.*/SPEC-([0-9]{4}).*#\1#p' | sort -n | tail -n1)
n=$(printf '%04d' $((10#$n + 1)))
cat > "specs/SPEC-$n-make-lint.md" <<SPEC
# SPEC-$n: Make Lint

## Functional requirements

\`make lint\` checks file names, titles, relative links, and the priority table's order.

## Non-functional requirements

Fast and dependency-free.

## Definition of done

1. \`make lint\` fails on each kind of violation and passes on the repo.
SPEC
row="| [SPEC-$n](SPEC-$n-make-lint.md) | SPEC-0003 | 3 | Make lint: check Markdown conventions | Low | Open |"
{ grep -vE '^\| \[SPEC-' specs/PRIORITIES.md | sed -e "s/^updated_at: .*/updated_at: $EVAL_TODAY/"; } > /tmp/head.$$
{ grep -E '^\| \[SPEC-' specs/PRIORITIES.md; echo "$row"; } |
  awk -F'|' '{ d = ($6 ~ /Low/) ? 1 : ($6 ~ /Medium/) ? 2 : 3; printf "%06d%d\t%s\n", $4, d, $0 }' | sort -s -k1,1 | cut -f2- > /tmp/rows.$$
cat /tmp/head.$$ /tmp/rows.$$ > specs/PRIORITIES.md
rm /tmp/head.$$ /tmp/rows.$$
