// Results are NDJSON, one line per case, variant, model, and repetition.
// Graded runs go to <name>.jsonl; infra failures, timeouts, truncation, refusals, and
// model mismatches go to <name>.infra.jsonl and never count as model failures.
import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const slug = (s) => s.replace(/[^a-zA-Z0-9.-]+/g, "_");

export function resultsFile(dir, date, harness, model, variant) {
  return join(dir, `${date}-${variant ? slug(variant) + "-" : ""}${harness}-${slug(model)}.jsonl`);
}

// Transcripts are git-ignored (results/transcripts/), one folder per run start, harness, model, and variant.
export function transcriptsDir(dir, started, harness, model, variant) {
  const stamp = started.toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
  return join(dir, "transcripts", `${stamp}-${variant ? slug(variant) + "-" : ""}${harness}-${slug(model)}`);
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

// One row per group (harness, model, variant): pass rate with the pass-rate range across cases' repetitions,
// cost per completed task, and means with min-max for tokens, turns, and time.
export function summarize(records, infra = []) {
  const groups = new Map();
  const key = (r) => `${r.experiment ?? ""}|${r.variant ?? ""}|${r.harness}|${r.model}`;
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
    const rate = (split) => {
      const xs = rs.filter((r) => (r.split ?? "train") === split);
      return xs.length ? xs.filter((r) => r.pass).length / xs.length : null;
    };
    return {
      experiment: r0.experiment ?? null,
      variant: r0.variant ?? null,
      harness: r0.harness,
      model: r0.model,
      runs: rs.length,
      infra: n,
      cases: reps.size,
      reps: rs.length ? Math.min(...[...reps.values()].map((v) => v.length)) : 0,
      pass_rate: rs.length ? passes.length / rs.length : null,
      // Train is what gets tuned on; test holds out whole kinds of task and is the number to report.
      train_pass_rate: rate("train"),
      test_pass_rate: rate("test"),
      // Spread: the range of per-repetition pass rates, so a difference smaller than this is noise.
      pass_rate_range: repRange(rs),
      cost_per_completed: passes.length && costs.length === rs.length ? costs.reduce((a, b) => a + b, 0) / passes.length : null,
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
const pct = (x) => (x === null || x === undefined ? "-" : `${Math.round(x * 100)}%`);

export function table(rows) {
  const lines = [
    "| Harness | Model | Variant | Pass rate (rep range) | Train | Test | Runs (cases x reps) | Infra | Cost per completed task | Tokens in / out | Turns | Time (s) |",
    "|---|---|---|---|---|---|---|---|---|---|---|---|",
  ];
  for (const s of rows) {
    lines.push(`| ${s.harness} | ${s.model} | ${s.variant ?? "-"} | ${pct(s.pass_rate)} (${s.pass_rate_range ? s.pass_rate_range.map(pct).join("-") : "-"}) | ${pct(s.train_pass_rate)} | ${pct(s.test_pass_rate)} | ${s.runs} (${s.cases} x ${s.reps}) | ${s.infra} | ${s.cost_per_completed === null ? "-" : "$" + fmt(s.cost_per_completed, 4)} | ${fmt(s.tokens_in, 0)} / ${fmt(s.tokens_out, 0)} | ${fmt(s.turns, 1)} | ${fmt(s.wall_s, 1)} |`);
  }
  return lines.join("\n");
}

// Failed runs grouped by case and harness (and model), most failures first, each with its transcript path,
// like fastai's most_confused: read these, not the pass rate, to decide what to change.
export function failures(records) {
  const groups = new Map();
  for (const r of records) {
    const k = `${r.case}|${r.harness}|${r.model}`;
    if (!groups.has(k)) groups.set(k, { case: r.case, split: r.split ?? "train", harness: r.harness, model: r.model, runs: 0, failed: [] });
    const g = groups.get(k);
    g.runs++;
    if (r.pass === false) g.failed.push(r);
  }
  return [...groups.values()]
    .filter((g) => g.failed.length)
    .sort((a, b) => b.failed.length / b.runs - a.failed.length / a.runs || b.failed.length - a.failed.length || a.case.localeCompare(b.case));
}

export function failuresText(groups) {
  if (!groups.length) return "No failures.";
  return groups.map((g) => [
    `${g.case} (${g.split}) ${g.harness} ${g.model}: ${g.failed.length} of ${g.runs} failed`,
    ...g.failed.map((r) => `  #${r.rep} ${r.date} ${r.transcript ?? "(no transcript)"}${r.grader_note ? "\n    " + r.grader_note.split("\n").pop() : ""}`),
  ].join("\n")).join("\n");
}
