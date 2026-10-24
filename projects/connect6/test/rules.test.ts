import { describe, expect, it } from "bun:test";
import {
	applyMove,
	createBoard,
	createGame,
	findWinningLine,
	type Position,
	place,
	validateMove,
} from "../src/core/index.js";

const row0 = (cols: number[]): Position[] =>
	cols.map((col) => ({ row: 0, col }));

describe("win detection (REQ-WIN)", () => {
	it("AC-WIN-1: six in a horizontal row is a win", () => {
		const board = place(createBoard(19), row0([0, 1, 2, 3, 4, 5]), "black");
		const line = findWinningLine(board, 19, "black", [{ row: 0, col: 5 }]);
		expect(line).not.toBeNull();
		expect(line?.length).toBeGreaterThanOrEqual(6);
	});

	it("AC-WIN-1: six on a diagonal is a win", () => {
		const diag = [0, 1, 2, 3, 4, 5].map((i) => ({ row: i, col: i }));
		const board = place(createBoard(19), diag, "white");
		const line = findWinningLine(board, 19, "white", [{ row: 5, col: 5 }]);
		expect(line?.length).toBeGreaterThanOrEqual(6);
	});

	it("five in a row is not a win", () => {
		const board = place(createBoard(19), row0([0, 1, 2, 3, 4]), "black");
		expect(
			findWinningLine(board, 19, "black", [{ row: 0, col: 4 }]),
		).toBeNull();
	});

	it("AC-WIN-3: an overline (seven) also wins", () => {
		const board = place(createBoard(19), row0([0, 1, 2, 3, 4, 5, 6]), "black");
		const line = findWinningLine(board, 19, "black", [{ row: 0, col: 6 }]);
		expect(line?.length).toBeGreaterThanOrEqual(6);
	});
});

describe("move legality (REQ-MOVE / REQ-TURN)", () => {
	it("AC-TURN-1 / AC-MOVE-1: opening move must place exactly one stone", () => {
		const game = createGame();
		expect(validateMove(game, { positions: row0([0]) }).ok).toBe(true);
		expect(validateMove(game, { positions: row0([0, 1]) }).ok).toBe(false);
	});

	it("AC-TURN-2: after the opening, a move must place exactly two stones", () => {
		const afterOpening = applyMove(createGame(), { positions: row0([9]) });
		expect(validateMove(afterOpening, { positions: row0([0, 1]) }).ok).toBe(
			true,
		);
		expect(validateMove(afterOpening, { positions: row0([0]) }).ok).toBe(false);
	});

	it("AC-MOVE-2: positions off the board are rejected", () => {
		const game = createGame();
		expect(validateMove(game, { positions: [{ row: -1, col: 0 }] }).ok).toBe(
			false,
		);
	});

	it("AC-MOVE-3: occupied cells are rejected", () => {
		const afterOpening = applyMove(createGame(), { positions: row0([0]) });
		const result = validateMove(afterOpening, { positions: row0([0, 1]) });
		expect(result.ok).toBe(false);
	});

	it("AC-MOVE-4: a position repeated within a move is rejected", () => {
		const afterOpening = applyMove(createGame(), { positions: row0([9]) });
		const result = validateMove(afterOpening, {
			positions: [
				{ row: 1, col: 1 },
				{ row: 1, col: 1 },
			],
		});
		expect(result.ok).toBe(false);
	});
});
