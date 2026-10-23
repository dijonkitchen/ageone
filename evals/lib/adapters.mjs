// One adapter per harness. Each runs one case in its sandbox and returns the same fields:
//   { status, served_model, tokens_in, tokens_out, cache_read, cost_usd, turns, stop_reason, output, error,
//     transcript, transcript_ext }
// transcript is the run's full record (pi session, Claude Code output, or the direct request and response),
// which the runner saves outside the results lines.
// status is "ok" when the run finished and can be graded, else one of
// "infra_error", "timeout", "truncated", "refused", "model_mismatch", which never count as model failures.
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { WEB_SEARCH_PATH, ensureTool, openRouterRouting, piAgentModels } from "../../harness/config.mjs";
import { runProcess, scriptEnv } from "./sandbox.mjs";

// Only these variables reach a harness: no cloud credentials, tokens, or the caller's own model settings.
const KEY_VARS = [
  "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY",
  "EXA_API_KEY", "PARALLEL_API_KEY", "BRAVE_API_KEY", "TAVILY_API_KEY", "PERPLEXITY_API_KEY",
];
const PASS_VARS = [
  "PATH", "LANG", "LC_ALL", "TERM", "TZ", "TMPDIR",
  "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "https_proxy", "http_proxy", "no_proxy",
  "SSL_CERT_FILE", "NODE_EXTRA_CA_CERTS", "REQUESTS_CA_BUNDLE",
];

export function cleanEnv(home, extra = {}) {
  const env = { HOME: home, CI: "1" };
  for (const k of [...PASS_VARS, ...KEY_VARS]) if (process.env[k]) env[k] = process.env[k];
  return { ...env, ...extra };
}

// Compare the requested model with the one the provider says it served, ignoring
// provider prefixes, `:variant` suffixes, date stamps, and `.` versus `-` in versions.
export function sameModel(requested, served) {
  const norm = (s) => s.split("/").pop().replace(/:.*$/, "").replace(/-\d{8}$/, "").replace(/\./g, "-").toLowerCase();
  return norm(requested) === norm(served);
}

function empty() {
  return { status: "ok", served_model: null, tokens_in: 0, tokens_out: 0, cache_read: 0, cost_usd: 0, turns: 0, stop_reason: null, output: "", error: null, transcript: "", transcript_ext: "txt" };
}

const pi = {
  name: "pi",
  version: (config) => config.harnesses.pi.version,
  async run({ caseDef, box, model, config, runDir, timeoutMs }) {
    const bin = ensureTool(config.harnesses.pi);
    const agentDir = join(runDir, "pi-agent");
    if (!existsSync(join(agentDir, "models.json"))) {
      mkdirSync(agentDir, { recursive: true });
      const models = piAgentModels(config);
      // Tests add a local mock provider through this file; real runs leave it unset.
      if (process.env.EVALS_PI_EXTRA_MODELS) {
        Object.assign(models.providers, JSON.parse(readFileSync(process.env.EVALS_PI_EXTRA_MODELS, "utf8")).providers);
      }
      writeFileSync(join(agentDir, "models.json"), JSON.stringify(models, null, 2));
      const web = JSON.parse(readFileSync(WEB_SEARCH_PATH, "utf8"));
      // Behind an HTTP proxy, let the extension skip its local DNS check for proxied hosts.
      if (process.env.HTTPS_PROXY) web.ssrf = { trustEnvProxy: true };
      writeFileSync(join(agentDir, "web-search.json"), JSON.stringify(web, null, 2));
    }
    const sessionDir = join(runDir, "sessions", `${model.full.replace(/[^a-zA-Z0-9.-]+/g, "_")}-${caseDef.id}-${box.rep}`);
    const args = ["--mode", "json", "--print", "--approve", "--model", model.full, "--session-dir", sessionDir];
    if (caseDef.mode === "direct") args.push("--no-tools", "--no-context-files", "--no-extensions", "--no-skills");
    args.push("--", caseDef.prompt);
    const env = cleanEnv(join(runDir, "home"), { PI_CODING_AGENT_DIR: agentDir, PI_SKIP_VERSION_CHECK: "1", PI_TELEMETRY: "0" });

    const r = empty();
    let lastAssistant = null;
    const proc = await runProcess(bin, args, {
      cwd: box.work, env, timeoutMs,
      onLine(line, kill) {
        let ev;
        try { ev = JSON.parse(line); } catch { return; }
        if (ev.type === "turn_end") {
          r.turns++;
          if (r.turns >= caseDef.maxTurns) kill("max_turns");
        }
        if (ev.type === "auto_retry_end" && ev.success === false) r.error = ev.finalError;
        if (ev.type === "message_end" && ev.message?.role === "assistant") {
          const m = ev.message;
          lastAssistant = m;
          r.tokens_in += (m.usage?.input ?? 0) + (m.usage?.cacheRead ?? 0) + (m.usage?.cacheWrite ?? 0);
          r.cache_read += m.usage?.cacheRead ?? 0;
          r.tokens_out += m.usage?.output ?? 0;
          r.cost_usd += m.usage?.cost?.total ?? 0;
          if (m.stopReason !== "error") r.served_model ??= m.responseModel ?? m.model;
        }
      },
    });
    // The pi session file is the transcript; fall back to the JSON event stream if pi wrote none.
    const sessions = existsSync(sessionDir) ? readdirSync(sessionDir).filter((f) => f.endsWith(".jsonl")).sort() : [];
    r.transcript = sessions.length ? sessions.map((f) => readFileSync(join(sessionDir, f), "utf8")).join("") : proc.stdout;
    r.transcript_ext = "jsonl";
    const m = lastAssistant;
    r.output = (m?.content ?? []).filter((c) => c.type === "text").map((c) => c.text).join("");
    r.stop_reason = proc.killedFor ?? m?.stopReason ?? null;
    if (proc.killedFor === "timeout") r.status = "timeout";
    else if (proc.killedFor === "max_turns") r.status = "ok";
    else if (!m || m.stopReason === "error" || proc.code !== 0) {
      r.status = "infra_error";
      r.error = m?.errorMessage ?? r.error ?? proc.stderr.slice(-2000);
    } else if (m.stopReason === "length") r.status = "truncated";
    else if (/refus|content_filter|safety/i.test(m.rawStopReason ?? "")) r.status = "refused";
    if (r.status === "ok" && r.served_model && !sameModel(model.id, r.served_model)) r.status = "model_mismatch";
    return r;
  },
};

// Claude Code in print mode. OpenRouter serves it through its Anthropic-compatible endpoint.
const claudeCode = {
  name: "claude-code",
  version: (config) => config.harnesses["claude-code"].version,
  async run({ caseDef, box, model, config, runDir, timeoutMs }) {
    const bin = ensureTool(config.harnesses["claude-code"]);
    const home = join(runDir, "home");
    const extra = { CLAUDE_CONFIG_DIR: join(home, ".claude"), IS_SANDBOX: "1", DISABLE_AUTOUPDATER: "1", CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: "1" };
    if (model.provider === "openrouter") {
      Object.assign(extra, { ANTHROPIC_BASE_URL: "https://openrouter.ai/api", ANTHROPIC_AUTH_TOKEN: process.env.OPENROUTER_API_KEY ?? "", ANTHROPIC_API_KEY: "" });
    } else if (model.provider !== "anthropic") {
      return { ...empty(), status: "infra_error", error: `claude-code supports anthropic and openrouter models, not ${model.provider}` };
    }
    const args = ["-p", caseDef.prompt, "--output-format", "json", "--model", model.id,
      "--max-turns", String(caseDef.maxTurns), "--dangerously-skip-permissions"];
    if (caseDef.mode === "direct") args.push("--tools", "");
    const proc = await runProcess(bin, args, { cwd: box.work, env: cleanEnv(home, extra), timeoutMs });
    const r = { ...empty(), transcript: proc.stdout + (proc.stderr ? `\n${proc.stderr}` : ""), transcript_ext: "json" };
    let out;
    try { out = JSON.parse(proc.stdout.trim().split("\n").pop()); } catch { out = null; }
    if (proc.killedFor === "timeout") return { ...r, status: "timeout", stop_reason: "timeout" };
    if (!out || (out.is_error && out.subtype !== "error_max_turns")) {
      return { ...r, status: "infra_error", error: (out?.result ?? proc.stderr ?? "").slice(-2000) };
    }
    const u = out.usage ?? {};
    r.tokens_in = (u.input_tokens ?? 0) + (u.cache_read_input_tokens ?? 0) + (u.cache_creation_input_tokens ?? 0);
    r.cache_read = u.cache_read_input_tokens ?? 0;
    r.tokens_out = u.output_tokens ?? 0;
    r.cost_usd = out.total_cost_usd ?? 0;
    r.turns = out.num_turns ?? 0;
    r.stop_reason = out.subtype === "error_max_turns" ? "max_turns" : out.stop_reason ?? out.subtype;
    r.output = out.result ?? "";
    // Claude Code also calls a small model for housekeeping; the requested model must be among those served.
    const served = Object.keys(out.modelUsage ?? {});
    r.served_model = served.find((s) => sameModel(model.id, s)) ?? served.join(",");
    if (!served.some((s) => sameModel(model.id, s))) r.status = "model_mismatch";
    return r;
  },
};

// One model call with no harness and no tools, for single-call cases such as reading or writing a data format.
const direct = {
  name: "direct",
  version: () => "1",
  async run({ caseDef, model, config, timeoutMs }) {
    const r = { ...empty(), turns: 1, transcript_ext: "json" };
    if (caseDef.mode !== "direct") return { ...r, status: "skip" };
    const base = process.env.EVALS_DIRECT_BASE_URL ?? {
      openrouter: "https://openrouter.ai/api/v1",
      openai: "https://api.openai.com/v1",
    }[model.provider];
    const key = process.env.EVALS_DIRECT_API_KEY ?? process.env[`${model.provider.toUpperCase()}_API_KEY`];
    if (!base) return { ...r, status: "infra_error", error: `direct mode supports openrouter and openai, not ${model.provider}` };
    const body = { model: model.id, messages: [{ role: "user", content: caseDef.prompt }] };
    if (model.provider === "openrouter") Object.assign(body, { provider: openRouterRouting(config, model), usage: { include: true } });
    let res, json;
    const record = (response) => JSON.stringify({ request: body, response }, null, 2);
    try {
      res = await fetch(`${base}/chat/completions`, {
        method: "POST",
        headers: { "content-type": "application/json", authorization: `Bearer ${key ?? ""}` },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(timeoutMs),
      });
      json = await res.json();
    } catch (err) {
      return { ...r, status: err.name === "TimeoutError" ? "timeout" : "infra_error", error: String(err), transcript: record({ error: String(err) }) };
    }
    r.transcript = record(json);
    if (!res.ok || json.error) return { ...r, status: "infra_error", error: JSON.stringify(json.error ?? json).slice(0, 2000) };
    const choice = json.choices?.[0];
    r.output = choice?.message?.content ?? "";
    r.stop_reason = choice?.finish_reason ?? null;
    r.served_model = json.model ?? null;
    r.tokens_in = json.usage?.prompt_tokens ?? 0;
    r.cache_read = json.usage?.prompt_tokens_details?.cached_tokens ?? 0;
    r.tokens_out = json.usage?.completion_tokens ?? 0;
    r.cost_usd = json.usage?.cost ?? null;
    if (r.stop_reason === "length") r.status = "truncated";
    else if (r.stop_reason === "content_filter") r.status = "refused";
    else if (!r.served_model || !sameModel(model.id, r.served_model)) r.status = "model_mismatch";
    return r;
  },
};

// Grader checks: `reference` applies the case's known-good solution and must pass;
// `null` does nothing and must fail. Neither calls a model.
const reference = {
  name: "reference",
  version: () => "1",
  async run({ caseDef, box, timeoutMs }) {
    const proc = await runProcess("bash", [join(caseDef.dir, "reference.sh")], { cwd: box.work, env: scriptEnv(caseDef), timeoutMs });
    const transcript = proc.stdout + proc.stderr;
    if (proc.code !== 0) return { ...empty(), status: "infra_error", error: proc.stderr.slice(-2000), transcript };
    return { ...empty(), served_model: "reference", output: proc.stdout, transcript };
  },
};

const nothing = {
  name: "null",
  version: () => "1",
  async run() {
    return { ...empty(), served_model: "null" };
  },
};

export const ADAPTERS = { pi, "claude-code": claudeCode, direct, reference, null: nothing };
