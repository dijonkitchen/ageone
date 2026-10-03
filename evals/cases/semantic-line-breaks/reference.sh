awk '/^```/ { code = !code } !code && !/^```/ { gsub(/[.!?] /, "&\n") } { print }' "$CASE_DIR/fixture.md" | sed -E 's/ +$//' > docs/decisions/2026-09-20-cache-policy.md
