import { describe, expect, it } from "bun:test";
import {
	applyMove,
	createBoard,
	createGame,
	type GameState,
	HeuristicAgent,
	MctsAgent,
	mulberry32,
	type Position,
	place,
	RandomAgent,
	validateMove,
} from "../src/core/index.js";
import { playMatch } from "../src/match.js";

const stateWith = (
	stones: { black?: Position[]; white?: Position[] },
	toMove: GameState["toMove"],
): GameState => {
	let board = createBoard(19);
	board = place(board, stones.black ?? [], "black");
	board = place(board, stones.white ?? [], "white");
	return {
		size: 19,
		board,
		toMove,
		status: "in_progress",
		winningLine: null,
		moveCount: 9,
		history: [],
	};
};

const row = (r: number, cols: number[]): Position[] =>
	cols.map((col) => ({ row: r, col }));
const fast = (seed: number) =>
	new MctsAgent({ rng: mulberry32(seed), iterations: 60 });

describe("MctsAgent (REQ-PLAYERS)", () => {
	it("AC-PLAYERS-5: plays both stones of a turn as one legal move", () => {
		const opening = createGame();
		const first = fast(1).search(opening);
		expect(first.positions).toHaveLength(1);
		expect(validateMove(opening, first).ok).toBe(true);
		const state = stateWith(
			{ black: row(9, [9, 10]), white: row(10, [9]) },
			"white",
		);
		const move = fast(1).search(state);
		expect(move.positions).toHaveLength(2);
		expect(validateMove(state, move).ok).toBe(true);
	});

	it("AC-PLAYERS-5: completes a two-stone win", () => {
		// Black has four on row 5; two more stones on that row win.
		const state = stateWith(
			{ black: row(5, [4, 5, 6, 7]), white: row(12, [1, 3, 5, 7, 9]) },
			"black",
		);
		const move = fast(2).search(state);
		expect(applyMove(state, move).status).toBe("black_won");
	});

	it("AC-PLAYERS-5: blocks a four the opponent could finish next turn", () => {
		const state = stateWith(
			{ black: row(3, [3, 4, 5, 6]), white: [{ row: 15, col: 15 }] },
			"white",
		);
		const move = fast(3).search(state);
		const blocked = (cols: number[]) =>
			move.positions.some((p) => p.row === 3 && cols.includes(p.col));
		// Every window of six through the four needs one white stone: one on
		// each side covers them all.
		expect(blocked([0, 1, 2])).toBe(true);
		expect(blocked([7, 8, 9])).toBe(true);
	});

	it("AC-PLAYERS-6: the same seed gives the same move", async () => {
		const state = stateWith(
			{ black: row(9, [8, 9, 10]), white: row(10, [9, 10]) },
			"white",
		);
		expect(fast(7).search(state)).toEqual(fast(7).search(state));
		const random = (seed: number) =>
			new RandomAgent(mulberry32(seed)).chooseMove(state);
		expect(await random(4)).toEqual(await random(4));
	});

	it("beats the heuristic player in seeded games, alternating colours", async () => {
		let wins = 0;
		const games = 10;
		for (let seed = 1; seed <= games; seed += 1) {
			const mctsBlack = seed % 2 === 1;
			const mcts = fast(seed);
			const heuristic = new HeuristicAgent();
			const result = await playMatch(
				mctsBlack ? mcts : heuristic,
				mctsBlack ? heuristic : mcts,
			);
			if (result.winner === (mctsBlack ? "black" : "white")) wins += 1;
		}
		expect(wins).toBeGreaterThanOrEqual(0.8 * games);
	});
});
