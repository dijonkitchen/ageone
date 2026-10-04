/**
 * Core domain types for Connect6.
 *
 * See specs/connect6.spec.md. These types are pure data: no methods, no
 * behaviour. Behaviour lives in board.ts / rules.ts / game.ts.
 */

/** Default board edge length (a standard Go board). AC-BOARD-1. */
export const DEFAULT_BOARD_SIZE = 19;

/** Run length required to win. AC-WIN-1. */
export const WIN_LENGTH = 6;

/** A player colour. Black moves first. AC-BOARD-2. */
export type Player = "black" | "white";

/** Cell content: a player's stone, or empty. */
export type Cell = Player | null;

/** A board coordinate; both fields are in [0, size). */
export interface Position {
	readonly row: number;
	readonly col: number;
}

/** The stones a player commits on a single turn. */
export interface Move {
	readonly positions: readonly Position[];
}

/** Terminal or ongoing status of a game. */
export type GameStatus = "in_progress" | "black_won" | "white_won" | "draw";

/**
 * A complete, immutable snapshot of a game. Applying a move yields a new
 * GameState; the previous one is never mutated (AC-MOVE-5).
 */
export interface GameState {
	readonly size: number;
	/** Row-major grid; board[row][col]. */
	readonly board: ReadonlyArray<ReadonlyArray<Cell>>;
	/** Whose turn it is. Meaningful only when status === "in_progress". */
	readonly toMove: Player;
	readonly status: GameStatus;
	/** The winning run when status is *_won, else null (AC-WIN-2). */
	readonly winningLine: readonly Position[] | null;
	/** Number of completed moves; drives the required stone count (AC-TURN-4). */
	readonly moveCount: number;
	readonly history: readonly Move[];
}

export const otherPlayer = (p: Player): Player =>
	p === "black" ? "white" : "black";

export const samePosition = (a: Position, b: Position): boolean =>
	a.row === b.row && a.col === b.col;

export const positionKey = (p: Position): string => `${p.row},${p.col}`;
