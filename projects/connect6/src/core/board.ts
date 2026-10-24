/**
 * Board primitives: construction, bounds, reads, and immutable writes.
 * Pure functions only (constitution §3, §4).
 */

import type { Cell, Player, Position } from "./types.js";

export const createBoard = (size: number): Cell[][] =>
	Array.from({ length: size }, () =>
		Array.from({ length: size }, () => null as Cell),
	);

export const inBounds = (size: number, pos: Position): boolean =>
	pos.row >= 0 && pos.row < size && pos.col >= 0 && pos.col < size;

export const cellAt = (
	board: ReadonlyArray<ReadonlyArray<Cell>>,
	pos: Position,
): Cell => board[pos.row]?.[pos.col] ?? null;

export const isEmpty = (
	board: ReadonlyArray<ReadonlyArray<Cell>>,
	pos: Position,
): boolean => cellAt(board, pos) === null;

/**
 * Returns a new board with `player` placed at each position. Does not
 * mutate the input (AC-MOVE-5). Callers are responsible for legality;
 * see rules.ts.
 */
export const place = (
	board: ReadonlyArray<ReadonlyArray<Cell>>,
	positions: readonly Position[],
	player: Player,
): Cell[][] => {
	const next = board.map((row) => row.slice());
	for (const pos of positions) {
		const r = next[pos.row];
		if (r) r[pos.col] = player;
	}
	return next;
};

export const countEmpty = (
	board: ReadonlyArray<ReadonlyArray<Cell>>,
): number => {
	let n = 0;
	for (const row of board) for (const cell of row) if (cell === null) n += 1;
	return n;
};

export const emptyPositions = (
	board: ReadonlyArray<ReadonlyArray<Cell>>,
): Position[] => {
	const out: Position[] = [];
	for (let row = 0; row < board.length; row += 1) {
		const cols = board[row];
		if (!cols) continue;
		for (let col = 0; col < cols.length; col += 1) {
			if (cols[col] === null) out.push({ row, col });
		}
	}
	return out;
};
