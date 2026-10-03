// Parse the answer as RFC 4180 CSV and compare it with the expected rows.
import { readFileSync } from "node:fs";

function parse(text) {
  const rows = [];
  let row = [], field = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"' && field === "") quoted = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field); rows.push(row); row = []; field = "";
    } else field += c;
  }
  if (field !== "" || row.length) { row.push(field); rows.push(row); }
  return rows.filter((r) => !(r.length === 1 && r[0] === ""));
}

const want = [
  ["id", "name", "status"],
  ["SPEC-0001", "Agent todo repo", "Done"],
  ["SPEC-0002", "Harness, models, and evals", "Open"],
  ["SPEC-0003", "Make setup", "Done"],
  ["SPEC-0004", "Eval pages", "Open"],
  ["SPEC-0005", 'Say "hi"', "Blocked (needs key)"],
];
const got = parse(readFileSync(process.argv[2], "utf8"));
if (JSON.stringify(got) !== JSON.stringify(want)) {
  console.log(`FAIL: rows differ\n${JSON.stringify(got)}`);
  process.exit(1);
}
