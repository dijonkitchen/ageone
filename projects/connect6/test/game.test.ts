import { describe, expect, it } from "bun:test";
import {
	applyMove,
	createGame,
	IllegalMoveError,
	isGameOver,
	type Move,
	type Position,
	requiredStones,
} from "../src/core/index.js";

const m = (...positions: Position[]): Move => ({ positions });
const p = (row: number, col: number): Position => ({ row, col });

describe("game lifecycle (REQ-BOARD / REQ-TURN)", () => {
	it("AC-BOARD-2: a new game has Black to move, in progress, no winner", () => {
		const game = createGame();
		expect(game.toMove).toBe("black");
		expect(game.status).toBe("in_progress");
		expect(game.winningLine).toBeNull();
		expect(game.moveCount).toBe(0);
	});

	it("AC-TURN-1/2: required stones is 1 on the opening, then 2", () => {
		const game = createGame();
		expect(requiredStones(game)).toBe(1);
		const next = applyMove(game, m(p(9, 9)));
		expect(requiredStones(next)).toBe(2);
	});

	it("AC-TURN-3: turn passes to the opponent after a non-terminal move", () => {
		const next = applyMove(createGame(), m(p(9, 9)));
		expect(next.toMove).toBe("white");
		expect(next.moveCount).toBe(1);
	});

	it("AC-MOVE-5: applyMove does not mutate the input state", () => {
		const game = createGame();
		const snapshot = JSON.stringify(game);
		applyMove(game, m(p(9, 9)));
		expect(JSON.stringify(game)).toBe(snapshot);
	});

	it("AC-MOVE-1: an illegal move throws IllegalMoveError", () => {
		const game = createGame();
		expect(() => applyMove(game, m(p(0, 0), p(0, 1)))).toThrow(
			IllegalMoveError,
		);
	});
});

describe("winning a game (REQ-WIN)", () => {
	it("AC-WIN-1/2: Black completing six in a row wins, with a winning line", () => {
		let g = createGame();
		g = applyMove(g, m(p(0, 0))); // B (opening, 1 stone)
		g = applyMove(g, m(p(18, 0), p(17, 0))); // W (scattered, no line)
		g = applyMove(g, m(p(0, 1), p(0, 2))); // B
		g = applyMove(g, m(p(18, 2), p(17, 2))); // W
		g = applyMove(g, m(p(0, 3), p(0, 4))); // B
		g = applyMove(g, m(p(18, 4), p(17, 4))); // W
		g = applyMove(g, m(p(0, 5), p(5, 5))); // B completes (0,0)..(0,5)

		expect(g.status).toBe("black_won");
		expect(isGameOver(g)).toBe(true);
		expect(g.winningLine?.length).toBeGreaterThanOrEqual(6);
	});

	it("AC-END-3: no further moves are allowed after the game ends", () => {
		let g = createGame();
		g = applyMove(g, m(p(0, 0)));
		g = applyMove(g, m(p(18, 0), p(17, 0)));
		g = applyMove(g, m(p(0, 1), p(0, 2)));
		g = applyMove(g, m(p(18, 2), p(17, 2)));
		g = applyMove(g, m(p(0, 3), p(0, 4)));
		g = applyMove(g, m(p(18, 4), p(17, 4)));
		g = applyMove(g, m(p(0, 5), p(5, 5))); // Black wins
		expect(() => applyMove(g, m(p(1, 1), p(1, 2)))).toThrow(IllegalMoveError);
	});
});

describe("draws (REQ-END)", () => {
	it("AC-END-2: a board that cannot fit the next move is a draw", () => {
		// 2×2 board: six in a row is impossible, so a full board draws.
		let g = createGame(2);
		g = applyMove(g, m(p(0, 0))); // B opening
		expect(g.status).toBe("in_progress");
		g = applyMove(g, m(p(0, 1), p(1, 0))); // W; one empty cell left, B needs two
		expect(g.status).toBe("draw");
		expect(isGameOver(g)).toBe(true);
	});

	it("AC-END-1: filling the board with no line is a draw", () => {
		// 3×3 board, nine cells, no six-in-a-row possible.
		let g = createGame(3);
		g = applyMove(g, m(p(0, 0)));
		g = applyMove(g, m(p(0, 1), p(0, 2)));
		g = applyMove(g, m(p(1, 0), p(1, 1)));
		g = applyMove(g, m(p(1, 2), p(2, 0)));
		g = applyMove(g, m(p(2, 1), p(2, 2)));
		expect(g.status).toBe("draw");
	});
});

describe("move counting and win triggers", () => {
	it("AC-TURN-4: moveCount counts completed moves and sets the stones required", () => {
		let g = createGame();
		g = applyMove(g, m(p(9, 9)));
		g = applyMove(g, m(p(0, 0), p(0, 1)));
		expect(g.moveCount).toBe(2);
		expect(g.history).toHaveLength(2);
		expect(requiredStones(g)).toBe(2);
	});

	it("AC-WIN-4: a move's stones can complete a run with earlier stones", () => {
		let g = createGame();
		g = applyMove(g, m(p(5, 0))); // B
		g = applyMove(g, m(p(18, 0), p(18, 2))); // W
		g = applyMove(g, m(p(5, 1), p(5, 2))); // B
		g = applyMove(g, m(p(18, 4), p(18, 6))); // W
		// Black's two new stones join three on the board: six in a row.
		g = applyMove(g, m(p(5, 4), p(5, 5)));
		expect(g.status).toBe("in_progress"); // gap at (5,3)
		g = applyMove(g, m(p(17, 0), p(17, 2))); // W
		g = applyMove(g, m(p(5, 3), p(10, 10)));
		expect(g.status).toBe("black_won");
		expect(g.winningLine).toHaveLength(6);
	});
});
