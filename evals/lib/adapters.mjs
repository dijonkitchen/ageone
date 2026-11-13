// One adapter per harness. Each runs one case in its sandbox and returns the same fields:
//   { status, served_model, served_hosts, tokens_in, tokens_out, cache_read, cost_usd, cost_source, turns, stop_reason, output, error }
// cost_source says where cost_usd came from: "gateway" (what the gateway billed, looked up per generation),
// "provider" (the API's own figure in its response), or the harness's estimate from list prices ("pi", "claude-code").
// status is "ok" when the run finished and can be graded, else one of
// "infra_error", "timeout", "truncated", "refused", "model_mismatch", which never count as model failures.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { GATEWAY_EXTENSION_PATH, WEB_SEARCH_PATH, claudeCodeEnv, directRequest, ensureTool, generationUrl, piAgentModels } from "../../harness/config.mjs";
import { runProcess, scriptEnv } from "./sandbox.mjs";

// Only these variables reach a harness: no cloud credentials, tokens, or the caller's own model settings.
const KEY_VARS = [
  "AI_GATEWAY_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY",
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
  return { status: "ok", served_model: null, served_hosts: null, tokens_in: 0, tokens_out: 0, cache_read: 0, cost_usd: 0, cost_source: null, turns: 0, stop_reason: null, output: "", error: null };
}

// What the gateway billed for these generations, summed, with the hosts that served them.
// Gateways record usage a few seconds after a response, so a "not found" is retried.
// Null when the route isn't a gateway or any ID can't be looked up; the caller then keeps the harness's figure.
export async function billedCost(config, model, ids, env = process.env) {
  // Both gateways' generation IDs start with gen- or gen_; anything else isn't one they can look up.
  if (!model.gateway || !ids.length || !ids.every((id) => /^gen[-_]/.test(id))) return null;
  const key = env[config.gateways[model.gateway].keyEnv] ?? "";
  const delay = Number(env.EVALS_LOOKUP_DELAY_MS ?? 2000);
  const lookup = async (id) => {
    for (let attempt = 0; attempt < 10; attempt++) {
      if (attempt) await new Promise((r) => setTimeout(r, delay));
      let res;
      try {
        res = await fetch(generationUrl(config, model, id, env), { headers: { authorization: `Bearer ${key}` }, signal: AbortSignal.timeout(30_000) });
      } catch {
        continue;
      }
      if (res.status === 404) continue;
      const json = await res.json().catch(() => null);
      const d = json?.data;
      if (res.ok && typeof d?.total_cost === "number") return { cost: d.total_cost, host: d.provider_name ?? null };
      if (!/not found/i.test(JSON.stringify(json?.error ?? json ?? ""))) return null;
    }
    return null;
  };
  const found = await Promise.all([...new Set(ids)].map(lookup));
  if (found.some((f) => f === null)) return null;
  return { cost: found.reduce((a, f) => a + f.cost, 0), hosts: [...new Set(found.map((f) => f.host).filter(Boolean))].sort() };
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
      // Tests add a local mock provider, or point a gateway's provider at one, through this file; real runs leave it unset.
      if (process.env.EVALS_PI_EXTRA_MODELS) {
        for (const [id, p] of Object.entries(JSON.parse(readFileSync(process.env.EVALS_PI_EXTRA_MODELS, "utf8")).providers)) {
          models.providers[id] = { ...models.providers[id], ...p };
        }
      }
      writeFileSync(join(agentDir, "models.json"), JSON.stringify(models, null, 2));
      const web = JSON.parse(readFileSync(WEB_SEARCH_PATH, "utf8"));
      // Behind an HTTP proxy, let the extension skip its local DNS check for proxied hosts.
      if (process.env.HTTPS_PROXY) web.ssrf = { trustEnvProxy: true };
      writeFileSync(join(agentDir, "web-search.json"), JSON.stringify(web, null, 2));
    }
    const args = ["--mode", "json", "--print", "--approve", "--provider", model.provider, "--model", model.id,
      "--session-dir", join(runDir, "sessions", `${caseDef.id}-${box.rep}`), "--extension", GATEWAY_EXTENSION_PATH];
    if (model.effort) args.push("--thinking", model.effort);
    // --no-extensions keeps the explicit --extension above.
    if (caseDef.mode === "direct") args.push("--no-tools", "--no-context-files", "--no-extensions", "--no-skills");
    args.push("--", caseDef.prompt);
    const env = cleanEnv(join(runDir, "home"), { PI_CODING_AGENT_DIR: agentDir, PI_SKIP_VERSION_CHECK: "1", PI_TELEMETRY: "0" });

    const r = { ...empty(), cost_source: "pi" };
    let lastAssistant = null;
    const responseIds = [];
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
          if (m.responseId) responseIds.push(m.responseId);
          if (m.stopReason !== "error") r.served_model ??= m.responseModel ?? m.model;
        }
      },
    });
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
    const billed = await billedCost(config, model, responseIds);
    if (billed) Object.assign(r, { cost_usd: billed.cost, cost_source: "gateway", served_hosts: billed.hosts });
    return r;
  },
};

// Claude Code in print mode, through a gateway's Claude Code endpoint or Anthropic's own API.
const claudeCode = {
  name: "claude-code",
  version: (config) => config.harnesses["claude-code"].version,
  async run({ caseDef, box, model, config, runDir, timeoutMs }) {
    const bin = ensureTool(config.harnesses["claude-code"]);
    const home = join(runDir, "home");
    const route = claudeCodeEnv(config, model);
    if (!route) return { ...empty(), status: "infra_error", error: `claude-code runs through a gateway or anthropic:<model>, not ${model.full}` };
    const extra = { CLAUDE_CONFIG_DIR: join(home, ".claude"), IS_SANDBOX: "1", DISABLE_AUTOUPDATER: "1", CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: "1", ...route };
    const args = ["-p", caseDef.prompt, "--output-format", "json", "--model", model.id,
      "--max-turns", String(caseDef.maxTurns), "--dangerously-skip-permissions"];
    if (caseDef.mode === "direct") args.push("--tools", "");
    const proc = await runProcess(bin, args, { cwd: box.work, env: cleanEnv(home, extra), timeoutMs });
    // Claude Code reports no request IDs, so its cost is its own estimate from list prices.
    const r = { ...empty(), cost_source: "claude-code" };
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
    const r = { ...empty(), turns: 1 };
    if (caseDef.mode !== "direct") return { ...r, status: "skip" };
    const req = directRequest(config, model, caseDef.prompt);
    if (!req) return { ...r, status: "infra_error", error: `direct mode needs an OpenAI-compatible API: a gateway or openai:<model>, not ${model.full}` };
    let res, json;
    try {
      res = await fetch(req.url, { method: "POST", headers: req.headers, body: JSON.stringify(req.body), signal: AbortSignal.timeout(timeoutMs) });
      json = await res.json();
    } catch (err) {
      return { ...r, status: err.name === "TimeoutError" ? "timeout" : "infra_error", error: String(err) };
    }
    if (!res.ok || json.error) return { ...r, status: "infra_error", error: JSON.stringify(json.error ?? json).slice(0, 2000) };
    const choice = json.choices?.[0];
    r.output = choice?.message?.content ?? "";
    r.stop_reason = choice?.finish_reason ?? null;
    r.served_model = json.model ?? null;
    r.tokens_in = json.usage?.prompt_tokens ?? 0;
    r.cache_read = json.usage?.prompt_tokens_details?.cached_tokens ?? 0;
    r.tokens_out = json.usage?.completion_tokens ?? 0;
    // OpenRouter puts its billed cost in the response; Vercel reports it through a lookup by generation ID.
    r.cost_usd = json.usage?.cost ?? null;
    r.cost_source = r.cost_usd === null ? null : model.gateway ? "gateway" : "provider";
    if (r.stop_reason === "length") r.status = "truncated";
    else if (r.stop_reason === "content_filter") r.status = "refused";
    else if (!r.served_model || !sameModel(model.id, r.served_model)) r.status = "model_mismatch";
    const billed = json.id ? await billedCost(config, model, [json.id]) : null;
    if (billed) Object.assign(r, { cost_usd: billed.cost, cost_source: "gateway", served_hosts: billed.hosts });
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
    if (proc.code !== 0) return { ...empty(), status: "infra_error", error: proc.stderr.slice(-2000) };
    return { ...empty(), served_model: "reference", output: proc.stdout };
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
