// Reads harness/models.json and turns it into what each harness needs.
// See docs/decisions/2026-09-26-vendor-neutral-ai-harness.md, section 3.
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

export function loadConfig(path = CONFIG_PATH) {
  return JSON.parse(readFileSync(path, "utf8"));
}

// A role name ("default") or a "provider/model" ID ("openrouter/deepseek/deepseek-v4.1-flash").
// The provider is everything before the first slash; OpenRouter model IDs keep their own slash.
export function resolveModel(config, roleOrId) {
  const full = config.roles[roleOrId] ?? roleOrId;
  const slash = full.indexOf("/");
  if (slash < 1) throw new Error(`not a role or provider/model ID: ${roleOrId}`);
  return {
    role: config.roles[roleOrId] ? roleOrId : null,
    full,
    provider: full.slice(0, slash),
    id: full.slice(slash + 1),
  };
}

export function isOpenWeight(config, model) {
  return model.provider === "openrouter" && config.openRouter.openWeightModels.includes(model.id.replace(/:.*$/, ""));
}

// OpenRouter's `provider` request field for a model: privacy for every model,
// plus the US/EU host allowlist for open-weight models (section 6 of the decision record).
export function openRouterRouting(config, model) {
  const routing = { ...config.openRouter.routing };
  if (isOpenWeight(config, model)) {
    routing.only = config.openRouter.openWeightHosts;
    routing.allow_fallbacks = false;
  }
  return routing;
}

// pi's user-level models.json: pi only reads it from its agent directory, so the eval runner
// and `harness/sync --agent-dir` write it there, generated from the roles file.
export function piAgentModels(config) {
  const modelOverrides = {};
  for (const id of config.openRouter.openWeightModels) {
    modelOverrides[id] = { compat: { openRouterRouting: openRouterRouting(config, { provider: "openrouter", id }) } };
  }
  return {
    providers: {
      openrouter: {
        compat: { openRouterRouting: { ...config.openRouter.routing } },
        modelOverrides,
      },
    },
  };
}

// The `default` role mirrored into pi's project settings, keeping every other key.
export function piProjectSettings(config, current = {}) {
  const model = resolveModel(config, "default");
  return { ...current, defaultProvider: model.provider, defaultModel: model.id };
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
