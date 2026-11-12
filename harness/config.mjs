// Reads harness/models.json and turns it into what each harness needs.
// See docs/decisions/2026-09-26-vendor-neutral-ai-harness.md, section 3,
// and docs/decisions/2026-11-12-model-gateway.md for the gateway table.
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
export const CONFIG_PATH = join(ROOT, "harness", "models.json");
export const PI_SETTINGS_PATH = join(ROOT, ".pi", "settings.json");
// pi-web-access reads its settings from pi's agent directory, like models.json.
export const WEB_SEARCH_PATH = join(ROOT, "harness", "web-search.json");
// The pi extension that adds gateway options pi can't send itself; .pi/settings.json lists it relative to .pi.
export const GATEWAY_EXTENSION_PATH = join(ROOT, "harness", "gateway-options.ts");
const GATEWAY_EXTENSION_SETTING = "../harness/gateway-options.ts";

export function loadConfig(path = CONFIG_PATH) {
  return JSON.parse(readFileSync(path, "utf8"));
}

// How each gateway takes privacy and host routing in a request. Everything else about a gateway
// (URLs, key, host names, model names) is data in harness/models.json, and this is the only code that names one.
const GATEWAY_API = {
  openrouter: {
    // OpenRouter reads a `provider` object; pi sends it from compat.openRouterRouting.
    routing: (gw, openWeight) => (openWeight ? { ...gw.routing, only: gw.openWeightHosts, allow_fallbacks: false } : { ...gw.routing }),
    piCompat: (routing) => ({ openRouterRouting: routing }),
    directFields: (routing) => ({ provider: routing, usage: { include: true } }),
    extraBody: null,
  },
  vercel: {
    // Vercel reads providerOptions.gateway. pi's Vercel provider speaks the Anthropic Messages API and sends
    // no gateway options, so harness/gateway-options.ts adds them, and Claude Code sends them as an extra body.
    // `only` is a hard filter: if no listed host can serve the model, the request fails.
    routing: (gw, openWeight) => ({ ...gw.routing, ...(openWeight ? { only: gw.openWeightHosts } : {}) }),
    piCompat: null,
    directFields: (routing) => ({ providerOptions: { gateway: routing } }),
    extraBody: (routing) => ({ providerOptions: { gateway: routing } }),
  },
};

// Keys for a vendor's own API, used with a `<vendor>:<model>` ID such as anthropic:claude-sonnet-5.
const VENDOR_KEYS = { anthropic: "ANTHROPIC_API_KEY", openai: "OPENAI_API_KEY", google: "GEMINI_API_KEY" };
// Vendors whose own API is OpenAI-compatible, for direct mode.
const VENDOR_OPENAI_URLS = { openai: "https://api.openai.com/v1" };

function gatewayApi(name) {
  const api = GATEWAY_API[name];
  if (!api) throw new Error(`no request format for gateway ${name}; add one to GATEWAY_API in harness/config.mjs`);
  return api;
}

// A role name ("default"), a gateway-neutral model ID ("deepseek/deepseek-v4.1-flash") on the active gateway,
// or a `<route>:<model>` ID, where the route is a gateway ("openrouter:deepseek/deepseek-v4.1-flash")
// or a pi provider for a vendor's own API ("anthropic:claude-sonnet-5").
// `gateway` overrides the active gateway for this call, as `--gateway` does on evals/run.
export function resolveModel(config, roleOrId, { gateway } = {}) {
  const role = Object.hasOwn(config.roles, roleOrId) ? roleOrId : null;
  const spec = role ? config.roles[role] : roleOrId;
  const effort = role ? config.effort?.[role] ?? null : null;
  const routed = spec.match(/^([a-z][a-z0-9-]*):(.+)$/);
  const route = routed ? routed[1] : gateway ?? config.gateway;
  const rest = routed ? routed[2] : spec;
  const gw = config.gateways[route];
  if (gw) {
    const owner = rest.split("/")[0];
    if (!rest.includes("/") || config.gateways[owner]) {
      const hint = config.gateways[owner] ? `; write the route with a colon: ${owner}:${rest.slice(owner.length + 1)}` : "";
      throw new Error(`not a role or creator/model ID: ${roleOrId}${hint}`);
    }
    return {
      role, route, gateway: route, full: `${route}:${rest}`, canonical: rest,
      provider: gw.piProvider, id: gw.modelIds?.[rest] ?? rest, keyEnv: gw.keyEnv, effort,
    };
  }
  if (!routed) throw new Error(`unknown gateway "${route}": set "gateway" in harness/models.json to one of ${Object.keys(config.gateways).join(", ")}`);
  return { role, route, gateway: null, full: spec, canonical: rest, provider: route, id: rest, keyEnv: VENDOR_KEYS[route] ?? null, effort };
}

export function isOpenWeight(config, model) {
  return Boolean(model.gateway) && config.openWeightModels.includes(model.canonical.replace(/:.*$/, ""));
}

// The gateway's privacy settings for every model, plus the US/EU host allowlist for open-weight models
// (section 6 of the vendor-neutral harness decision record). Null for a vendor's own API.
export function gatewayRouting(config, model) {
  if (!model.gateway) return null;
  return gatewayApi(model.gateway).routing(config.gateways[model.gateway], isOpenWeight(config, model));
}

// pi's user-level models.json: pi only reads it from its agent directory, so the eval runner
// and `harness/sync --agent-dir` write it there. Only gateways whose routing pi sends itself appear.
export function piAgentModels(config) {
  const providers = {};
  for (const [name, gw] of Object.entries(config.gateways)) {
    const { piCompat } = gatewayApi(name);
    if (!piCompat) continue;
    const modelOverrides = {};
    for (const canonical of config.openWeightModels) {
      const model = resolveModel(config, `${name}:${canonical}`);
      modelOverrides[model.id] = { compat: piCompat(gatewayRouting(config, model)) };
    }
    providers[gw.piProvider] = { compat: piCompat({ ...gw.routing }), modelOverrides };
  }
  return { providers };
}

// What harness/gateway-options.ts adds to a pi request: the gateway's options for gateways pi can't route
// itself, found from the pi provider and the request's model ID. Null when there is nothing to add.
export function piRequestFields(config, piProvider, modelId) {
  const name = Object.keys(config.gateways).find((n) => config.gateways[n].piProvider === piProvider);
  if (!name || !gatewayApi(name).extraBody) return null;
  const gw = config.gateways[name];
  const canonical = Object.keys(gw.modelIds ?? {}).find((k) => gw.modelIds[k] === modelId) ?? modelId;
  const model = resolveModel(config, `${name}:${canonical}`);
  return gatewayApi(name).extraBody(gatewayRouting(config, model));
}

// Merge request fields into a payload one object level deep at a time, so existing
// providerOptions.gateway keys (such as `order`) survive and ours win on a clash.
export function mergeFields(payload, fields) {
  const out = { ...payload };
  for (const [k, v] of Object.entries(fields)) {
    out[k] = v && typeof v === "object" && !Array.isArray(v) && out[k] && typeof out[k] === "object" ? mergeFields(out[k], v) : v;
  }
  return out;
}

// A direct-mode request: one OpenAI-compatible chat completion, with the gateway's privacy and host fields.
// EVALS_DIRECT_BASE_URL points it at a mock in tests. Null when the route has no OpenAI-compatible API.
export function directRequest(config, model, prompt, env = process.env) {
  const gw = model.gateway ? config.gateways[model.gateway] : null;
  const base = env.EVALS_DIRECT_BASE_URL ?? (gw ? gw.openaiBaseUrl : VENDOR_OPENAI_URLS[model.provider]);
  if (!base) return null;
  const key = env.EVALS_DIRECT_API_KEY ?? (model.keyEnv ? env[model.keyEnv] : undefined) ?? "";
  const body = { model: model.id, messages: [{ role: "user", content: prompt }] };
  if (gw) Object.assign(body, gatewayApi(model.gateway).directFields(gatewayRouting(config, model)));
  return { url: `${base}/chat/completions`, headers: { "content-type": "application/json", authorization: `Bearer ${key}` }, body };
}

// Where a gateway reports what it billed for one generation (the chat completion or message ID).
export function generationUrl(config, model, id, env = process.env) {
  if (!model.gateway) return null;
  const base = env.EVALS_DIRECT_BASE_URL ?? config.gateways[model.gateway].openaiBaseUrl;
  return `${base}/generation?id=${encodeURIComponent(id)}`;
}

// Environment for Claude Code: a gateway's Claude Code endpoint and key, its extra settings, and its
// privacy and host options as an extra request body where the gateway reads them from the body.
// Empty for Anthropic's own API (ANTHROPIC_API_KEY); null when Claude Code can't use the route.
export function claudeCodeEnv(config, model, env = process.env) {
  if (!model.gateway) return model.provider === "anthropic" ? {} : null;
  const gw = config.gateways[model.gateway];
  const out = { ANTHROPIC_BASE_URL: gw.claudeCodeBaseUrl, ANTHROPIC_AUTH_TOKEN: env[gw.keyEnv] ?? "", ANTHROPIC_API_KEY: "", ...gw.claudeCodeEnv };
  const { extraBody } = gatewayApi(model.gateway);
  if (extraBody) out.CLAUDE_CODE_EXTRA_BODY = JSON.stringify(extraBody(gatewayRouting(config, model)));
  return out;
}

// The `default` role mirrored into pi's project settings, keeping every other key.
export function piProjectSettings(config, current = {}) {
  const model = resolveModel(config, "default");
  const out = { ...current, defaultProvider: model.provider, defaultModel: model.id };
  if (model.effort) out.defaultThinkingLevel = model.effort;
  else delete out.defaultThinkingLevel;
  out.extensions = [...new Set([...(current.extensions ?? []), GATEWAY_EXTENSION_SETTING])];
  return out;
}

// npm packages are installed once per version under ~/.cache/ageone/tools; returns the install folder.
export function ensurePackage({ package: pkg, version }) {
  const prefix = join(process.env.XDG_CACHE_HOME ?? join(homedir(), ".cache"), "ageone", "tools", `${pkg.replace("/", "+")}@${version}`);
  if (!existsSync(join(prefix, "node_modules", ...pkg.split("/"), "package.json"))) {
    mkdirSync(prefix, { recursive: true });
    console.error(`installing ${pkg}@${version}`);
    execFileSync("npm", ["install", "--prefix", prefix, "--no-save", "--no-audit", "--no-fund", `${pkg}@${version}`], { stdio: ["ignore", 2, 2] });
  }
  return prefix;
}

// Harness CLIs come from the versions pinned in harness/models.json; returns the CLI's path.
export function ensureTool(tool) {
  return join(ensurePackage(tool), "node_modules", ".bin", tool.bin);
}
