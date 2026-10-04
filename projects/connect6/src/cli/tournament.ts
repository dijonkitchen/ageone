/**
 * Headless tournament: every pair of the given players meets over seeded
 * games, swapping colours each game, and each game becomes one NDJSON line.
 *
 *   bun run tournament --players mcts,heuristic --games 100
 *   bun run tournament --players llm,heuristic --games 4 --role cheap
 */

import { appendFileSync } from "node:fs";
import { parseArgs } from "node:util";
import {
	type Agent,
	HeuristicAgent,
	LlmAgent,
	MctsAgent,
	mulberry32,
	RandomAgent,
} from "../core/index.js";
import { playMatch } from "../match.js";
import {
	estimateCost,
	modelForRole,
	openRouterChat,
	type RoleModel,
	TURNS_PER_GAME,
} from "./openrouter.js";

export const PLAYER_KINDS = ["random", "heuristic", "mcts", "llm"] as const;
export type PlayerKind = (typeof PLAYER_KINDS)[number];

export interface TournamentOptions {
	readonly players: readonly PlayerKind[];
	readonly games: number;
	readonly seed: number;
	readonly size: number;
	readonly iterations: number;
	readonly role: string;
}

export interface GameRecord {
	readonly seed: number;
	readonly black: string;
	readonly white: string;
	readonly winner: "black" | "white" | "draw";
	readonly winnerPlayer: string | null;
	readonly reason: "six" | "draw" | "forfeit";
	readonly moves: number;
	readonly ms: number;
	readonly tokens: { readonly black: number; readonly white: number };
	readonly cost: { readonly black: number; readonly white: number };
	readonly model?: string;
}

export const makeAgent = (
	kind: PlayerKind,
	seed: number,
	options: Pick<TournamentOptions, "iterations">,
	llm: () => LlmAgent,
): Agent => {
	switch (kind) {
		case "random":
			return new RandomAgent(mulberry32(seed));
		case "heuristic":
			return new HeuristicAgent();
		case "mcts":
			return new MctsAgent({
				rng: mulberry32(seed),
				iterations: options.iterations,
			});
		case "llm":
			return llm();
	}
};

/** Each unordered pair of players, playing `games` games with colours swapped. */
export const schedule = (
	players: readonly PlayerKind[],
	games: number,
	seed: number,
): { black: PlayerKind; white: PlayerKind; seed: number }[] => {
	const out: { black: PlayerKind; white: PlayerKind; seed: number }[] = [];
	for (let i = 0; i < players.length; i += 1) {
		for (let j = i + 1; j < players.length; j += 1) {
			const a = players[i];
			const b = players[j];
			if (!a || !b) continue;
			for (let g = 0; g < games; g += 1) {
				const [black, white] = g % 2 === 0 ? [a, b] : [b, a];
				out.push({ black, white, seed: seed + g });
			}
		}
	}
	return out;
};

export async function* runTournament(
	options: TournamentOptions,
	llm: () => LlmAgent,
	model?: string,
): AsyncGenerator<GameRecord> {
	for (const game of schedule(options.players, options.games, options.seed)) {
		// Different streams per colour so a mirror match isn't one game twice.
		const black = makeAgent(game.black, game.seed * 2, options, llm);
		const white = makeAgent(game.white, game.seed * 2 + 1, options, llm);
		const started = performance.now();
		const result = await playMatch(black, white, options.size);
		const usage = (a: Agent) => a.usage ?? { tokens: 0, cost: 0 };
		yield {
			seed: game.seed,
			black: game.black,
			white: game.white,
			winner: result.winner,
			winnerPlayer:
				result.winner === "draw"
					? null
					: result.winner === "black"
						? game.black
						: game.white,
			reason: result.reason,
			moves: result.state.moveCount,
			ms: Math.round(performance.now() - started),
			tokens: { black: usage(black).tokens, white: usage(white).tokens },
			cost: { black: usage(black).cost, white: usage(white).cost },
			...(model ? { model } : {}),
		};
	}
}

const main = async (): Promise<void> => {
	const { values } = parseArgs({
		options: {
			players: { type: "string", default: "mcts,heuristic" },
			games: { type: "string", default: "10" },
			seed: { type: "string", default: "1" },
			size: { type: "string", default: "19" },
			iterations: { type: "string", default: "300" },
			role: { type: "string", default: "cheap" },
			out: { type: "string" },
		},
	});
	const players = values.players.split(",").map((p) => p.trim());
	for (const p of players) {
		if (!PLAYER_KINDS.includes(p as PlayerKind)) {
			throw new Error(`unknown player ${p}; use ${PLAYER_KINDS.join(", ")}`);
		}
	}
	const options: TournamentOptions = {
		players: players as PlayerKind[],
		games: Number(values.games),
		seed: Number(values.seed),
		size: Number(values.size),
		iterations: Number(values.iterations),
		role: values.role,
	};
	const games = schedule(options.players, options.games, options.seed);
	let target: RoleModel | undefined;
	if (options.players.includes("llm")) {
		target = modelForRole(options.role);
		const llmSides = games.reduce(
			(n, g) => n + (g.black === "llm" ? 1 : 0) + (g.white === "llm" ? 1 : 0),
			0,
		);
		const turns = llmSides * TURNS_PER_GAME;
		const cost = await estimateCost(target.model, turns);
		console.error(
			`${games.length} games; LLM ${target.model} (role ${options.role}) plays about ${turns} turns, ` +
				(cost === null
					? "cost unknown (price list unavailable)."
					: `estimated $${cost.toFixed(4)}.`),
		);
	} else {
		console.error(`${games.length} games; no LLM players, no cost.`);
	}
	const chosen = target;
	const llm = () => {
		if (!chosen) throw new Error("no LLM role loaded");
		return new LlmAgent(openRouterChat(chosen), { name: "llm" });
	};
	for await (const record of runTournament(options, llm, target?.model)) {
		const line = JSON.stringify(record);
		if (values.out) appendFileSync(values.out, `${line}\n`);
		else console.log(line);
	}
};

if (import.meta.main) await main();
