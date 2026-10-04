/**
 * Model access for the LLM player, outside the pure core: reads the role's
 * model from the repo's harness/models.json and calls OpenRouter with the
 * config's routing settings. Never put a model ID in code.
 */

import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import type { Chat, ChatMessage } from "../core/index.js";

export interface ModelsConfig {
	readonly roles: Record<string, string>;
	readonly openRouter?: { readonly routing?: Record<string, unknown> };
}

export const OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions";

/** CONNECT6_MODELS, else the nearest harness/models.json above `start`. */
export const findModelsConfig = (start = process.cwd()): string => {
	const fromEnv = process.env.CONNECT6_MODELS;
	if (fromEnv) return fromEnv;
	for (let dir = start; ; dir = dirname(dir)) {
		const candidate = join(dir, "harness", "models.json");
		if (existsSync(candidate)) return candidate;
		if (dirname(dir) === dir) break;
	}
	throw new Error("harness/models.json not found; set CONNECT6_MODELS");
};

export interface RoleModel {
	readonly role: string;
	/** OpenRouter model id, without the "openrouter/" prefix. */
	readonly model: string;
	readonly routing: Record<string, unknown>;
}

export const modelForRole = (
	role: string,
	config: ModelsConfig = JSON.parse(readFileSync(findModelsConfig(), "utf8")),
): RoleModel => {
	const ref = config.roles[role];
	if (!ref) throw new Error(`no model role "${role}" in harness/models.json`);
	const [provider, ...rest] = ref.split("/");
	if (provider !== "openrouter") {
		throw new Error(`role ${role} uses ${ref}; only openrouter/ models work`);
	}
	return {
		role,
		model: rest.join("/"),
		routing: config.openRouter?.routing ?? {},
	};
};

type Fetch = (url: string, init: RequestInit) => Promise<Response>;

export const openRouterChat = (
	target: RoleModel,
	apiKey: string | undefined = process.env.OPENROUTER_API_KEY,
	fetcher: Fetch = fetch,
): Chat => {
	return async (messages: readonly ChatMessage[]) => {
		if (!apiKey) throw new Error("OPENROUTER_API_KEY is not set");
		const response = await fetcher(OPENROUTER_URL, {
			method: "POST",
			headers: {
				Authorization: `Bearer ${apiKey}`,
				"Content-Type": "application/json",
				"X-Title": "Connect6",
			},
			body: JSON.stringify({
				model: target.model,
				messages,
				provider: target.routing,
				usage: { include: true },
			}),
		});
		if (!response.ok) {
			throw new Error(
				`OpenRouter ${response.status}: ${await response.text()}`,
			);
		}
		const data = (await response.json()) as {
			choices?: { message?: { content?: string | null } }[];
			usage?: { total_tokens?: number; cost?: number };
		};
		return {
			content: data.choices?.[0]?.message?.content ?? "",
			tokens: data.usage?.total_tokens ?? 0,
			cost: data.usage?.cost ?? 0,
		};
	};
};

/** Rough tokens per LLM turn: the board, the prompt, and a short reply. */
export const TOKENS_PER_TURN = 1_200;
/** Rough LLM turns per game (games run about 15 to 40 turns a side). */
export const TURNS_PER_GAME = 30;

/**
 * Estimated USD for `turns` LLM turns, from OpenRouter's public price list;
 * null when prices can't be fetched.
 */
export const estimateCost = async (
	model: string,
	turns: number,
	fetcher: Fetch = fetch,
): Promise<number | null> => {
	try {
		const response = await fetcher("https://openrouter.ai/api/v1/models", {
			method: "GET",
		});
		const data = (await response.json()) as {
			data?: {
				id: string;
				pricing?: { prompt?: string; completion?: string };
			}[];
		};
		const entry = data.data?.find((m) => m.id === model);
		if (!entry?.pricing) return null;
		const prompt = Number(entry.pricing.prompt ?? 0);
		const completion = Number(entry.pricing.completion ?? 0);
		// Assume most tokens are prompt; replies stay short.
		return turns * TOKENS_PER_TURN * (0.85 * prompt + 0.15 * completion);
	} catch {
		return null;
	}
};
