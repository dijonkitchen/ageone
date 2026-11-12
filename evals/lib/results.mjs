// Results are NDJSON, one line per case, variant, model, and repetition.
// Graded runs go to <name>.jsonl; infra failures, timeouts, truncation, refusals, and
// model mismatches go to <name>.infra.jsonl and never count as model failures.
import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

export function resultsFile(dir, date, harness, model, variant) {
  const slug = (s) => s.replace(/[^a-zA-Z0-9.-]+/g, "_");
  return join(dir, `${date}-${variant ? slug(variant) + "-" : ""}${harness}-${slug(model)}.jsonl`);
}

export function append(file, record) {
  mkdirSync(join(file, ".."), { recursive: true });
  const target = record.status === "ok" ? file : file.replace(/\.jsonl$/, ".infra.jsonl");
  appendFileSync(target, JSON.stringify(record) + "\n");
}

export function readRecords(files) {
  return files.flatMap((f) =>
    readFileSync(f, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l)),
  );
}

const mean = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
const range = (xs) => (xs.length ? [Math.min(...xs), Math.max(...xs)] : null);

// A record's model label carries its route (vercel:anthropic/claude-sonnet-5), so two gateways never share a row.
// poolRoutes drops the route to compare one model across gateways in a single row.
const modelLabel = (r, poolRoutes) => (poolRoutes && r.route && r.model.startsWith(`${r.route}:`) ? r.model.slice(r.route.length + 1) : r.model);

// One row per group (harness, model, variant): pass rate with the pass-rate range across cases' repetitions,
// cost per completed task, and means with min-max for tokens, turns, and time.
export function summarize(records, infra = [], { poolRoutes = false } = {}) {
  const groups = new Map();
  const key = (r) => `${r.experiment ?? ""}|${r.variant ?? ""}|${r.harness}|${modelLabel(r, poolRoutes)}`;
  for (const r of records) {
    if (!groups.has(key(r))) groups.set(key(r), { records: [], infra: 0 });
    groups.get(key(r)).records.push(r);
  }
  for (const r of infra) groups.get(key(r)) ? groups.get(key(r)).infra++ : groups.set(key(r), { records: [], infra: 1, first: r });
  return [...groups.values()].map(({ records: rs, infra: n, first }) => {
    const r0 = rs[0] ?? first;
    const passes = rs.filter((r) => r.pass);
    const costs = rs.map((r) => r.cost_usd).filter((c) => c !== null && c !== undefined);
    const reps = new Map();
    for (const r of rs) reps.set(r.case, [...(reps.get(r.case) ?? []), r.pass ? 1 : 0]);
    return {
      experiment: r0.experiment ?? null,
      variant: r0.variant ?? null,
      harness: r0.harness,
      model: modelLabel(r0, poolRoutes),
      runs: rs.length,
      infra: n,
      cases: reps.size,
      reps: rs.length ? Math.min(...[...reps.values()].map((v) => v.length)) : 0,
      pass_rate: rs.length ? passes.length / rs.length : null,
      // Spread: the range of per-repetition pass rates, so a difference smaller than this is noise.
      pass_rate_range: repRange(rs),
      cost_per_completed: passes.length && costs.length === rs.length ? costs.reduce((a, b) => a + b, 0) / passes.length : null,
      // True when any run's cost is a harness's or provider's estimate rather than what the gateway billed.
      cost_estimated: rs.some((r) => r.cost_source && r.cost_source !== "gateway"),
      tokens_in: mean(rs.map((r) => r.tokens_in)),
      tokens_out: mean(rs.map((r) => r.tokens_out)),
      turns: mean(rs.map((r) => r.turns)),
      turns_range: range(rs.map((r) => r.turns)),
      wall_s: mean(rs.map((r) => r.wall_ms / 1000)),
      wall_s_range: range(rs.map((r) => r.wall_ms / 1000)),
    };
  });
}

function repRange(rs) {
  const byRep = new Map();
  for (const r of rs) byRep.set(r.rep, [...(byRep.get(r.rep) ?? []), r.pass ? 1 : 0]);
  return range([...byRep.values()].map(mean));
}

const fmt = (x, d = 2) => (x === null || x === undefined ? "-" : Number(x).toFixed(d));
const pct = (x) => (x === null ? "-" : `${Math.round(x * 100)}%`);

export function table(rows) {
  const lines = [
    "| Harness | Model | Variant | Pass rate (rep range) | Runs (cases x reps) | Infra | Cost per completed task | Tokens in / out | Turns | Time (s) |",
    "|---|---|---|---|---|---|---|---|---|---|",
  ];
  for (const s of rows) {
    const cost = s.cost_per_completed === null ? "-" : `$${fmt(s.cost_per_completed, 4)}${s.cost_estimated ? " *" : ""}`;
    lines.push(`| ${s.harness} | ${s.model} | ${s.variant ?? "-"} | ${pct(s.pass_rate)} (${s.pass_rate_range ? s.pass_rate_range.map(pct).join("-") : "-"}) | ${s.runs} (${s.cases} x ${s.reps}) | ${s.infra} | ${cost} | ${fmt(s.tokens_in, 0)} / ${fmt(s.tokens_out, 0)} | ${fmt(s.turns, 1)} | ${fmt(s.wall_s, 1)} |`);
  }
  if (rows.some((s) => s.cost_estimated && s.cost_per_completed !== null)) {
    lines.push("", "\\* Includes the harness's own cost estimate from list prices where the gateway's billed cost wasn't available.");
  }
  return lines.join("\n");
}
