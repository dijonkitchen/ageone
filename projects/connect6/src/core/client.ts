/**
 * Transport abstraction (REQ-CLIENT). The UI talks to a `GameClient`, never
 * to the engine directly. Today the only implementation runs in-memory; a
 * networked backend is a future `GameClient` whose methods await `fetch`.
 * Because the interface is async, swapping local for remote needs no UI
 * changes (NFR-3).
 */

import { applyMove, createGame } from "./game.js";
import type { GameState, Move } from "./types.js";
import { DEFAULT_BOARD_SIZE } from "./types.js";

export interface GameClient {
	getState(): Promise<GameState>;
	applyMove(move: Move): Promise<GameState>;
	reset(): Promise<GameState>;
}

/** In-memory client backed by the pure engine. AC-CLIENT-2. */
export class LocalGameClient implements GameClient {
	private state: GameState;

	constructor(private readonly size: number = DEFAULT_BOARD_SIZE) {
		this.state = createGame(size);
	}

	async getState(): Promise<GameState> {
		return this.state;
	}

	async applyMove(move: Move): Promise<GameState> {
		// applyMove throws IllegalMoveError on invalid input, surfacing the
		// same reasons the core uses (AC-CLIENT-2).
		this.state = applyMove(this.state, move);
		return this.state;
	}

	async reset(): Promise<GameState> {
		this.state = createGame(this.size);
		return this.state;
	}
}
