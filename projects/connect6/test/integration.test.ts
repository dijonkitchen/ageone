import { describe, expect, it } from "bun:test";
import {
	type Agent,
	applyMove,
	createGame,
	type GameState,
	HeuristicAgent,
	isGameOver,
	RandomAgent,
} from "../src/core/index.js";

/** Deterministic PRNG so self-play games are reproducible. */
const mulberry32 = (seed: number) => {
	let state = seed;
	return () => {
		state = (state + 0x6d2b79f5) | 0;
		let t = Math.imul(state ^ (state >>> 15), 1 | state);
		t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
};

/** Plays a full game through `applyMove`, which throws on any illegal move. */
const playGame = async (
	black: Agent,
	white: Agent,
	size: number,
): Promise<GameState> => {
	let state = createGame(size);
	let safety = size * size + 5; // upper bound on moves; guards against loops
	while (!isGameOver(state) && safety > 0) {
		const agent = state.toMove === "black" ? black : white;
		state = applyMove(state, await agent.chooseMove(state));
		safety -= 1;
	}
	return state;
};

describe("self-play (REQ-PLAYERS, end-to-end)", () => {
	it("AC-PLAYERS-2: heuristic-vs-random games finish with only legal moves", async () => {
		for (let seed = 1; seed <= 4; seed += 1) {
			const result = await playGame(
				new HeuristicAgent(),
				new RandomAgent(mulberry32(seed)),
				19,
			);
			expect(isGameOver(result)).toBe(true);
		}
	});

	it("games on a small board always terminate", async () => {
		const result = await playGame(
			new RandomAgent(mulberry32(7)),
			new RandomAgent(mulberry32(8)),
			7,
		);
		expect(isGameOver(result)).toBe(true);
	});
});
