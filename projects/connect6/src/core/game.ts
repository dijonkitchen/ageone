/**
 * The Connect6 state machine: create a game and apply moves to produce new
 * immutable states. Pure (constitution §3, §4).
 *
 * Traces: REQ-BOARD, REQ-TURN, REQ-WIN, REQ-END.
 */

import { createBoard, place } from "./board.js";
import { findWinningLine, stonesRequired, validateMove } from "./rules.js";
import type { GameState, GameStatus, Move, Player } from "./types.js";
import { DEFAULT_BOARD_SIZE, otherPlayer } from "./types.js";

export class IllegalMoveError extends Error {
	constructor(reason: string) {
		super(`illegal move: ${reason}`);
		this.name = "IllegalMoveError";
	}
}

/** Creates a fresh game with an empty board and Black to move. AC-BOARD-1/2. */
export const createGame = (size: number = DEFAULT_BOARD_SIZE): GameState => ({
	size,
	board: createBoard(size),
	toMove: "black",
	status: "in_progress",
	winningLine: null,
	moveCount: 0,
	history: [],
});

const wonStatus = (player: Player): GameStatus =>
	player === "black" ? "black_won" : "white_won";

/**
 * Applies a move for the current player, returning the next state. Throws
 * IllegalMoveError if the move violates REQ-MOVE / REQ-END. Never mutates
 * `state` (AC-MOVE-5).
 */
export const applyMove = (state: GameState, move: Move): GameState => {
	const legality = validateMove(state, move);
	if (!legality.ok) throw new IllegalMoveError(legality.reason);

	const mover = state.toMove;
	const board = place(state.board, move.positions, mover);
	const moveCount = state.moveCount + 1;
	const history = [...state.history, move];

	const winningLine = findWinningLine(board, state.size, mover, move.positions);
	if (winningLine) {
		return {
			...state,
			board,
			toMove: otherPlayer(mover),
			status: wonStatus(mover), // AC-WIN-1
			winningLine, // AC-WIN-2
			moveCount,
			history,
		};
	}

	const next = otherPlayer(mover);
	// After the opening move every turn needs 2 stones; if the opponent
	// cannot place that many, the game is drawn (AC-END-1/2).
	// Stones on the board: one opening stone, then two per move (NFR-4: no
	// board scan).
	const empty = state.size * state.size - (2 * moveCount - 1);
	const drawn = empty < 2;
	return {
		...state,
		board,
		toMove: next,
		status: drawn ? "draw" : "in_progress",
		winningLine: null,
		moveCount,
		history,
	};
};

export const isGameOver = (state: GameState): boolean =>
	state.status !== "in_progress";

/** Convenience: how many stones the current player must place. AC-TURN-1/2. */
export const requiredStones = (state: GameState): number =>
	stonesRequired(state);
