/**
 * Baseline agent: places the required number of stones on random empty
 * cells. Useful as an opponent floor and as a control in eval/outcome
 * comparisons. Always returns a legal move (AC-PLAYERS-2).
 */

import { emptyPositions } from "../board.js";
import { requiredStones } from "../game.js";
import type { GameState, Move, Position } from "../types.js";
import type { Agent, Rng } from "./agent.js";

export class RandomAgent implements Agent {
	readonly name = "random";

	constructor(private readonly rng: Rng = Math.random) {}

	async chooseMove(state: GameState): Promise<Move> {
		const empties = emptyPositions(state.board);
		const required = requiredStones(state);
		const positions: Position[] = [];
		const pool = empties.slice();
		for (let i = 0; i < required && pool.length > 0; i += 1) {
			const idx = Math.floor(this.rng() * pool.length);
			const [picked] = pool.splice(idx, 1);
			if (picked) positions.push(picked);
		}
		return { positions };
	}
}

/** Small seeded PRNG (mulberry32), so seeded games replay exactly. */
export const mulberry32 = (seed: number): Rng => {
	let state = seed | 0;
	return () => {
		state = (state + 0x6d2b79f5) | 0;
		let t = Math.imul(state ^ (state >>> 15), 1 | state);
		t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
};
