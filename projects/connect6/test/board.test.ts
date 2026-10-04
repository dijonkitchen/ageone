import { describe, expect, it } from "bun:test";
import {
	cellAt,
	countEmpty,
	createBoard,
	emptyPositions,
	inBounds,
	place,
} from "../src/core/index.js";

describe("board", () => {
	it("AC-BOARD-1: createBoard makes an N×N grid of empty cells", () => {
		const board = createBoard(19);
		expect(board).toHaveLength(19);
		expect(board.every((row) => row.length === 19)).toBe(true);
		expect(countEmpty(board)).toBe(19 * 19);
		expect(emptyPositions(board)).toHaveLength(361);
	});

	it("inBounds rejects coordinates outside [0, size)", () => {
		expect(inBounds(19, { row: 0, col: 0 })).toBe(true);
		expect(inBounds(19, { row: 18, col: 18 })).toBe(true);
		expect(inBounds(19, { row: -1, col: 0 })).toBe(false);
		expect(inBounds(19, { row: 0, col: 19 })).toBe(false);
	});

	it("AC-MOVE-5: place returns a new board and never mutates the input", () => {
		const board = createBoard(19);
		const next = place(board, [{ row: 3, col: 3 }], "black");
		expect(cellAt(next, { row: 3, col: 3 })).toBe("black");
		// Original is untouched.
		expect(cellAt(board, { row: 3, col: 3 })).toBe(null);
		expect(next).not.toBe(board);
	});
});
