// The formats compared, each with a renderer (what the model reads), a writing instruction
// (what the model writes), and a parser for grading what it wrote.
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { ensurePackage } from "../../../harness/config.mjs";

export const FIELDS = ["id", "title", "team", "status", "hours"];
export const TOON = { package: "@toon-format/toon", version: "4.1.1" };

async function toon() {
  return import(pathToFileURL(join(ensurePackage(TOON), "node_modules", "@toon-format", "toon", "dist", "index.mjs")).href);
}

function csvField(v) {
  const s = String(v);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

// RFC 4180: quoted fields, doubled quotes, CRLF or LF line ends.
export function parseCsv(text) {
  const rows = [];
  let row = [], field = "", quoted = false, wasQuoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"' && field === "" && !wasQuoted) { quoted = true; wasQuoted = true; }
    else if (c === ",") { row.push(field); field = ""; wasQuoted = false; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field); rows.push(row); row = []; field = ""; wasQuoted = false;
    } else field += c;
  }
  if (field !== "" || row.length) { row.push(field); rows.push(row); }
  return rows.filter((r) => !(r.length === 1 && r[0] === ""));
}

function fromRows(rows) {
  const [header, ...body] = rows;
  return body.map((r) => Object.fromEntries(header.map((h, i) => [h.trim(), r[i]])));
}

function parseKv(text) {
  return text.trim().split(/\n\s*\n/).map((block) =>
    Object.fromEntries(block.split("\n").filter((l) => l.trim()).map((l) => {
      const i = l.indexOf(":");
      if (i < 0) throw new Error(`not a key: value line: ${l}`);
      return [l.slice(0, i).trim(), l.slice(i + 1).trim()];
    })),
  );
}

export const FORMATS = {
  csv: {
    label: "CSV",
    render: (rows) => [FIELDS.join(","), ...rows.map((r) => FIELDS.map((f) => csvField(r[f])).join(","))].join("\n"),
    write: `CSV with the header row ${FIELDS.join(",")} and RFC 4180 quoting`,
    parse: (text) => fromRows(parseCsv(text)),
  },
  toon: {
    label: "TOON",
    render: async (rows) => (await toon()).encode({ tasks: rows }),
    write: `TOON (Token-Oriented Object Notation), as a tabular array named tasks with the fields ${FIELDS.join(",")}`,
    parse: async (text) => (await toon()).decode(text).tasks,
  },
  ndjson: {
    label: "NDJSON",
    render: (rows) => rows.map((r) => JSON.stringify(r)).join("\n"),
    write: `NDJSON: one JSON object per line, with the keys ${FIELDS.join(", ")}`,
    parse: (text) => text.trim().split("\n").filter((l) => l.trim()).map((l) => JSON.parse(l)),
  },
  "json-min": {
    label: "Minified JSON",
    render: (rows) => JSON.stringify(rows),
    write: `a minified JSON array of objects with the keys ${FIELDS.join(", ")}`,
    parse: (text) => JSON.parse(text),
  },
  "json-pretty": {
    label: "Pretty JSON",
    render: (rows) => JSON.stringify(rows, null, 2),
    write: `a JSON array of objects with the keys ${FIELDS.join(", ")}, indented with 2 spaces`,
    parse: (text) => JSON.parse(text),
  },
  kv: {
    label: "key: value",
    render: (rows) => rows.map((r) => FIELDS.map((f) => `${f}: ${r[f]}`).join("\n")).join("\n\n"),
    write: `one block of \`key: value\` lines per task (${FIELDS.join(", ")}), with a blank line between tasks`,
    parse: parseKv,
  },
};

// Compare parsed records with the expected ones, field by field; hours compare as numbers.
export function sameRecords(got, want) {
  if (!Array.isArray(got) || got.length !== want.length) return `expected ${want.length} records, got ${Array.isArray(got) ? got.length : typeof got}`;
  for (let i = 0; i < want.length; i++) {
    for (const f of FIELDS) {
      const a = got[i]?.[f], b = want[i][f];
      const ok = f === "hours" ? Number(a) === Number(b) : String(a ?? "") === String(b);
      if (!ok) return `record ${i + 1} ${f}: expected ${JSON.stringify(b)}, got ${JSON.stringify(a)}`;
    }
  }
  return null;
}
