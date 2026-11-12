// pi extension: adds the active gateway's privacy and host options to each model request that pi can't route itself.
// pi's built-in Vercel provider speaks the Anthropic Messages API and sends no `providerOptions.gateway`, so without
// this a Vercel request would get only the team-wide settings: no per-request zero data retention and no host
// allowlist for open-weight models. OpenRouter needs nothing here, because pi sends its routing from models.json.
// Loaded by .pi/settings.json for pi in this repo, and with --extension by the eval runner.
import { loadConfig, mergeFields, piRequestFields } from "./config.mjs";

export default function (pi: any) {
  const config = loadConfig();
  pi.on("before_provider_request", (event: any, ctx: any) => {
    const payload = event.payload as Record<string, unknown>;
    try {
      const fields = piRequestFields(config, ctx.model?.provider, String(payload?.model ?? ctx.model?.id ?? ""));
      return fields ? mergeFields(payload, fields) : undefined;
    } catch (err) {
      // Fail closed: pi sends the original payload when a handler throws, so name a model no gateway serves instead.
      return { ...payload, model: `gateway-options-failed: ${err instanceof Error ? err.message : err}` };
    }
  });
}
