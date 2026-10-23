import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import type { Chat } from "./types.ts";

export interface ModelsConfig {
	readonly roles: Record<string, string>;
	readonly openRouter?: { readonly routing?: Record<string, unknown> };
}

export const OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions";

/** SONAL_MODELS, else the nearest harness/models.json above `start`. */
export const findModelsConfig = (start = process.cwd()): string => {
	if (process.env.SONAL_MODELS) return process.env.SONAL_MODELS;
	for (let dir = start; ; dir = dirname(dir)) {
		const candidate = join(dir, "harness", "models.json");
		if (existsSync(candidate)) return candidate;
		if (dirname(dir) === dir) break;
	}
	throw new Error("harness/models.json not found; set SONAL_MODELS");
};

/** The OpenRouter model for a role; a model ID never appears in this project's code. */
export const modelForRole = (role: string, config: ModelsConfig) => {
	const ref = config.roles[role];
	if (!ref) throw new Error(`no model role "${role}" in harness/models.json`);
	const [provider, ...rest] = ref.split("/");
	if (provider !== "openrouter") {
		throw new Error(`role ${role} uses ${ref}; only openrouter/ models work`);
	}
	return {
		model: rest.join("/"),
		routing: config.openRouter?.routing ?? {},
	};
};

type Fetch = (url: string, init: RequestInit) => Promise<Response>;

export const openRouterChat = (
	role: string,
	config: ModelsConfig = JSON.parse(readFileSync(findModelsConfig(), "utf8")),
	apiKey: string | undefined = process.env.OPENROUTER_API_KEY,
	fetcher: Fetch = fetch,
): Chat => {
	const target = modelForRole(role, config);
	return async (messages) => {
		if (!apiKey) throw new Error("OPENROUTER_API_KEY is not set");
		const response = await fetcher(OPENROUTER_URL, {
			method: "POST",
			headers: {
				Authorization: `Bearer ${apiKey}`,
				"Content-Type": "application/json",
				"X-Title": "Sonal",
			},
			body: JSON.stringify({
				model: target.model,
				messages,
				provider: target.routing,
				temperature: 0,
			}),
		});
		if (!response.ok) {
			throw new Error(
				`OpenRouter ${response.status}: ${await response.text()}`,
			);
		}
		const data = (await response.json()) as {
			choices?: { message?: { content?: string | null } }[];
		};
		return data.choices?.[0]?.message?.content ?? "";
	};
};
