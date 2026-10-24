import { describe, expect, it } from "bun:test";
import {
	applyMove,
	createBoard,
	createGame,
	type GameState,
	HeuristicAgent,
	type Position,
	place,
	positionKey,
	RandomAgent,
	validateMove,
} from "../src/core/index.js";

const containsPosition = (positions: readonly Position[], target: Position) =>
	positions.some((p) => positionKey(p) === positionKey(target));

const stateWith = (
	board: GameState["board"],
	toMove: GameState["toMove"],
	moveCount: number,
): GameState => ({
	size: 19,
	board,
	toMove,
	status: "in_progress",
	winningLine: null,
	moveCount,
	history: [],
});

const row0 = (cols: number[]): Position[] =>
	cols.map((col) => ({ row: 0, col }));

describe("RandomAgent (REQ-PLAYERS)", () => {
	it("AC-PLAYERS-2: returns a legal move of the required size", async () => {
		const agent = new RandomAgent(() => 0.5);

		const opening = createGame();
		const first = await agent.chooseMove(opening);
		expect(first.positions).toHaveLength(1);
		expect(validateMove(opening, first).ok).toBe(true);

		const next = applyMove(opening, first);
		const second = await agent.chooseMove(next);
		expect(second.positions).toHaveLength(2);
		expect(validateMove(next, second).ok).toBe(true);
	});
});

describe("HeuristicAgent (REQ-PLAYERS)", () => {
	it("AC-PLAYERS-3: completes an immediate win when one exists", async () => {
		const board = place(createBoard(19), row0([0, 1, 2, 3, 4]), "black");
		const state = stateWith(board, "black", 6);

		const move = await new HeuristicAgent().chooseMove(state);
		expect(containsPosition(move.positions, { row: 0, col: 5 })).toBe(true);

		// ...and playing it actually wins.
		const result = applyMove(state, move);
		expect(result.status).toBe("black_won");
	});

	it("AC-PLAYERS-4: blocks a single-ended immediate threat", async () => {
		// White has five in a row against the left edge; the only open end is
		// (0,5). Black has no win of its own, so it must block there.
		const board = place(createBoard(19), row0([0, 1, 2, 3, 4]), "white");
		const state = stateWith(board, "black", 6);

		const move = await new HeuristicAgent().chooseMove(state);
		expect(containsPosition(move.positions, { row: 0, col: 5 })).toBe(true);
	});
});
