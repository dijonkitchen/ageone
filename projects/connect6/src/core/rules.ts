/**
 * Game rules: how many stones a turn requires, whether a move is legal,
 * and whether a position completes a winning run.
 *
 * Traces: REQ-TURN, REQ-MOVE, REQ-WIN in specs/connect6.spec.md.
 */

import { cellAt, inBounds, isEmpty } from "./board.js";
import type { Cell, GameState, Move, Player, Position } from "./types.js";
import { positionKey, WIN_LENGTH } from "./types.js";

/** The four line axes a run can form along. */
const AXES: ReadonlyArray<readonly [number, number]> = [
	[0, 1], // horizontal
	[1, 0], // vertical
	[1, 1], // diagonal ↘
	[1, -1], // diagonal ↙
];

/** Stones required this turn: 1 for Black's opening move, otherwise 2. AC-TURN-1/2. */
export const stonesRequired = (state: GameState): number =>
	state.moveCount === 0 ? 1 : 2;

export type MoveLegality = { ok: true } | { ok: false; reason: string };

/** Validates a move against REQ-MOVE / REQ-END without applying it. */
export const validateMove = (state: GameState, move: Move): MoveLegality => {
	if (state.status !== "in_progress") {
		return { ok: false, reason: "game is over" }; // AC-END-3
	}

	const required = stonesRequired(state);
	if (move.positions.length !== required) {
		return {
			ok: false,
			reason: `move must place exactly ${required} stone(s), got ${move.positions.length}`,
		}; // AC-MOVE-1
	}

	const seen = new Set<string>();
	for (const pos of move.positions) {
		if (!inBounds(state.size, pos)) {
			return {
				ok: false,
				reason: `position ${positionKey(pos)} is off the board`,
			}; // AC-MOVE-2
		}
		const key = positionKey(pos);
		if (seen.has(key)) {
			return { ok: false, reason: `position ${key} is repeated in the move` }; // AC-MOVE-4
		}
		seen.add(key);
		if (!isEmpty(state.board, pos)) {
			return { ok: false, reason: `position ${key} is already occupied` }; // AC-MOVE-3
		}
	}

	return { ok: true };
};

/**
 * Returns the full run of `player` stones passing through `pos` along the
 * given axis, including `pos` itself. Assumes `pos` holds a `player` stone.
 */
const runThrough = (
	board: ReadonlyArray<ReadonlyArray<Cell>>,
	size: number,
	player: Player,
	pos: Position,
	axis: readonly [number, number],
): Position[] => {
	const [dr, dc] = axis;
	// Walk backward to the start of the run.
	let start = pos;
	for (;;) {
		const prev: Position = { row: start.row - dr, col: start.col - dc };
		if (inBounds(size, prev) && cellAt(board, prev) === player) start = prev;
		else break;
	}
	// Walk forward collecting the run.
	const run: Position[] = [];
	let cur = start;
	while (inBounds(size, cur) && cellAt(board, cur) === player) {
		run.push(cur);
		cur = { row: cur.row + dr, col: cur.col + dc };
	}
	return run;
};

/**
 * If any of `placed` lies on a run of WIN_LENGTH or more `player` stones,
 * returns that winning line; otherwise null. Checks only the lines through
 * the just-placed stones (AC-WIN-4) for efficiency (NFR-4). Overlines win
 * (AC-WIN-3) because the run length test is `>=`.
 */
export const findWinningLine = (
	board: ReadonlyArray<ReadonlyArray<Cell>>,
	size: number,
	player: Player,
	placed: readonly Position[],
): Position[] | null => {
	for (const pos of placed) {
		if (cellAt(board, pos) !== player) continue;
		for (const axis of AXES) {
			const run = runThrough(board, size, player, pos, axis);
			if (run.length >= WIN_LENGTH) return run;
		}
	}
	return null;
};
