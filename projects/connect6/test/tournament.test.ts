import { describe, expect, it } from "bun:test";
import { writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
	estimateCost,
	modelForRole,
	OPENROUTER_URL,
	openRouterChat,
} from "../src/cli/openrouter.js";
import {
	type GameRecord,
	runTournament,
	schedule,
	type TournamentOptions,
} from "../src/cli/tournament.js";
import { LlmAgent } from "../src/core/index.js";

const options: TournamentOptions = {
	players: ["random", "heuristic"],
	games: 2,
	seed: 5,
	size: 9,
	iterations: 30,
	role: "cheap",
};
const noLlm = (): LlmAgent => {
	throw new Error("no LLM in this tournament");
};
const collect = async (
	opts: TournamentOptions,
	llm: () => LlmAgent = noLlm,
): Promise<GameRecord[]> => {
	const out: GameRecord[] = [];
	for await (const record of runTournament(opts, llm)) out.push(record);
	return out;
};

describe("tournament (REQ-TOURNAMENT)", () => {
	it("AC-TOURNAMENT-1: every pair meets, swapping colours each game", () => {
		const games = schedule(["random", "heuristic", "mcts"], 2, 1);
		expect(games).toHaveLength(6);
		expect(games.slice(0, 2)).toEqual([
			{ black: "random", white: "heuristic", seed: 1 },
			{ black: "heuristic", white: "random", seed: 2 },
		]);
	});

	it("AC-TOURNAMENT-2: one record per game with players, winner, moves, time, tokens, and cost", async () => {
		const records = await collect(options);
		expect(records).toHaveLength(2);
		for (const r of records) {
			expect(Object.keys(r).sort()).toEqual(
				[
					"black",
					"cost",
					"moves",
					"ms",
					"reason",
					"seed",
					"tokens",
					"white",
					"winner",
					"winnerPlayer",
				].sort(),
			);
			expect(JSON.parse(JSON.stringify(r))).toEqual(r);
		}
	});

	it("AC-TOURNAMENT-3: the same seed gives the same games", async () => {
		const opts = { ...options, players: ["random", "mcts"] as const };
		const strip = (rs: GameRecord[]) => rs.map(({ ms: _, ...rest }) => rest);
		expect(strip(await collect(opts))).toEqual(strip(await collect(opts)));
	});

	it("LLM games record tokens and cost per side", async () => {
		const llm = () =>
			new LlmAgent(async () => ({ content: "pass", tokens: 50, cost: 0.001 }), {
				maxAttempts: 2,
			});
		const [record] = await collect(
			{ ...options, players: ["heuristic", "llm"], games: 1 },
			llm,
		);
		expect(record).toMatchObject({
			white: "llm",
			winner: "black",
			reason: "forfeit",
			tokens: { black: 0, white: 100 },
			cost: { black: 0, white: 0.002 },
		});
	});
});

describe("OpenRouter access", () => {
	const config = {
		roles: { cheap: "openrouter/acme/tiny", local: "ollama/llama" },
		openRouter: { routing: { zdr: true, data_collection: "deny" } },
	};

	it("picks the model by role from the models config", () => {
		const path = join(tmpdir(), "connect6-models.json");
		writeFileSync(path, JSON.stringify(config));
		process.env.CONNECT6_MODELS = path;
		try {
			expect(modelForRole("cheap")).toEqual({
				role: "cheap",
				model: "acme/tiny",
				routing: { zdr: true, data_collection: "deny" },
			});
		} finally {
			delete process.env.CONNECT6_MODELS;
		}
		expect(() => modelForRole("local", config)).toThrow("openrouter");
		expect(() => modelForRole("missing", config)).toThrow("no model role");
	});

	it("sends the model and routing, and reads usage", async () => {
		let sent: { url: string; body: Record<string, unknown> } | undefined;
		const chat = openRouterChat(
			modelForRole("cheap", config),
			"key",
			async (url, init) => {
				sent = { url, body: JSON.parse(String(init.body)) };
				return Response.json({
					choices: [{ message: { content: "MOVE: J10" } }],
					usage: { total_tokens: 42, cost: 0.0001 },
				});
			},
		);
		const reply = await chat([{ role: "user", content: "hi" }]);
		expect(reply).toEqual({ content: "MOVE: J10", tokens: 42, cost: 0.0001 });
		expect(sent?.url).toBe(OPENROUTER_URL);
		expect(sent?.body).toMatchObject({
			model: "acme/tiny",
			provider: { zdr: true, data_collection: "deny" },
		});
	});

	it("AC-TOURNAMENT-4: estimates cost from the public price list", async () => {
		const prices = async () =>
			Response.json({
				data: [
					{
						id: "acme/tiny",
						pricing: { prompt: "0.000001", completion: "0.000002" },
					},
				],
			});
		const cost = await estimateCost("acme/tiny", 10, prices);
		expect(cost).toBeCloseTo(10 * 1200 * (0.85e-6 + 0.15 * 2e-6));
		const down = async (): Promise<Response> => {
			throw new Error("offline");
		};
		expect(await estimateCost("acme/tiny", 10, down)).toBeNull();
	});
});
