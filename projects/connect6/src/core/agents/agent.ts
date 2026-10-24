/**
 * The Agent seam (REQ-PLAYERS). Human input and any programmatic player —
 * random, heuristic, MCTS, or an LLM behind an API — implement this one
 * interface, so they are interchangeable wherever a move is needed.
 */

import type { GameState, Move } from "../types.js";

export interface Agent {
	readonly name: string;
	/** Returns a legal move for `state` (AC-PLAYERS-2), or throws ForfeitError. */
	chooseMove(state: GameState): Promise<Move>;
	/** Tokens and cost (USD) spent so far, for players that call a model. */
	readonly usage?: { readonly tokens: number; readonly cost: number };
}

/** Pseudo-random source, injectable so agents can be made deterministic. */
export type Rng = () => number;

/** Thrown by a player that cannot produce a legal move; it loses the game. */
export class ForfeitError extends Error {
	constructor(readonly reason: string) {
		super(`forfeit: ${reason}`);
		this.name = "ForfeitError";
	}
}
