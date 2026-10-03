grep -qF '(docs/decisions/2026-09-26-conventions.md)' README.md || { echo "README.md no longer links to the conventions record"; exit 1; }
sed -i 's#(docs/decisions/2026-09-26-conventions.md)#(docs/decisions/2026-09-25-conventions.md)#' README.md
