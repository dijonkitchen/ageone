// Search and answering sit behind two small interfaces, so the fake ones drive M1 and the real ones M2.
import models from "../../../harness/models.json";
import type { Source } from "./note";
import { SYSTEM_PROMPT, sourcesBlock } from "./untrusted";

type Fetcher = (
	input: URL | RequestInfo,
	init?: RequestInit,
) => Promise<Response>;

export interface SearchProvider {
	search(query: string): Promise<Source[]>;
}

export interface AnswerProvider {
	readonly label: string;
	answer(question: string, sources: Source[]): Promise<string>;
}

export class FakeSearch implements SearchProvider {
	async search(query: string): Promise<Source[]> {
		return [1, 2].map((n) => ({
			title: `Fake result ${n} for ${query}`,
			url: `https://example.com/fake/${n}`,
			snippet: `A canned snippet ${n} about ${query}.`,
		}));
	}
}

export class FakeAnswer implements AnswerProvider {
	readonly label = "fake";
	async answer(question: string, sources: Source[]): Promise<string> {
		const cites = sources.map((_, i) => `[^${i + 1}]`).join("");
		return `A canned answer to “${question}”.${cites}`;
	}
}

// Kagi's search API has no browser CORS access, so it is reached through a proxy the user runs;
// the proxy holds the Kagi key and returns Kagi's JSON ({ data: [{ t: 0, title, url, snippet }] }).
export class KagiProxySearch implements SearchProvider {
	constructor(
		private proxyUrl: string,
		private fetcher: Fetcher = (...args) => fetch(...args),
	) {}
	async search(query: string): Promise<Source[]> {
		const url = new URL(this.proxyUrl);
		url.searchParams.set("q", query);
		const res = await this.fetcher(url);
		if (!res.ok) throw new Error(`search proxy answered ${res.status}`);
		const body = (await res.json()) as { data?: Record<string, unknown>[] };
		return (body.data ?? [])
			.filter((r) => r.t === 0 || r.t === undefined)
			.map((r) => ({
				title: String(r.title ?? r.url ?? ""),
				url: String(r.url ?? ""),
				snippet: String(r.snippet ?? ""),
			}))
			.filter((s) => /^https?:\/\//.test(s.url));
	}
}

// No proxy: the user pastes results, as blocks of "title", "url", "snippet" lines separated by a blank line.
export function parsePastedResults(text: string): Source[] {
	return text
		.split(/\n\s*\n/)
		.map((block) =>
			block
				.trim()
				.split("\n")
				.map((l) => l.trim()),
		)
		.map(([title = "", url = "", ...rest]) => ({
			title,
			url,
			snippet: rest.join(" "),
		}))
		.filter((s) => /^https?:\/\//.test(s.url));
}

export class PastedSearch implements SearchProvider {
	constructor(private text: string) {}
	async search(): Promise<Source[]> {
		return parsePastedResults(this.text);
	}
}

export type ModelChoice = {
	role: string;
	id: string;
	provider?: Record<string, unknown>;
};

// Roles come from harness/models.json; "private" is the open-weight model on the allowlisted hosts.
export function roleNames(): string[] {
	return [...Object.keys(models.roles).filter((r) => r !== "judge"), "private"];
}

export function resolveModel(role: string): ModelChoice {
	const { roles, openRouter } = models;
	const routing = { ...openRouter.routing };
	if (role === "private") {
		const id = openRouter.openWeightModels[0];
		if (!id) throw new Error("harness/models.json lists no open-weight model");
		return {
			role,
			id,
			provider: {
				...routing,
				only: openRouter.openWeightHosts,
				allow_fallbacks: false,
			},
		};
	}
	const configured = roles[role as keyof typeof roles];
	if (!configured) throw new Error(`unknown model role: ${role}`);
	return {
		role,
		id: configured.replace(/^openrouter\//, ""),
		provider: routing,
	};
}

export class OpenRouterAnswer implements AnswerProvider {
	readonly label: string;
	private choice: ModelChoice;
	constructor(
		role: string,
		private apiKey: string,
		private fetcher: Fetcher = (...args) => fetch(...args),
	) {
		this.choice = resolveModel(role);
		this.label = `${role} (${this.choice.id})`;
	}
	async answer(question: string, sources: Source[]): Promise<string> {
		const res = await this.fetcher(
			"https://openrouter.ai/api/v1/chat/completions",
			{
				method: "POST",
				headers: {
					"content-type": "application/json",
					authorization: `Bearer ${this.apiKey}`,
				},
				body: JSON.stringify({
					model: this.choice.id,
					provider: this.choice.provider,
					messages: [
						{ role: "system", content: SYSTEM_PROMPT },
						{
							role: "user",
							content: `Question: ${question}\n\nSources:\n${sourcesBlock(sources)}`,
						},
					],
				}),
			},
		);
		if (!res.ok) throw new Error(`model answered ${res.status}`);
		const body = (await res.json()) as {
			choices?: { message?: { content?: string } }[];
		};
		const text = body.choices?.[0]?.message?.content;
		if (!text) throw new Error("model returned no answer");
		return text;
	}
}
