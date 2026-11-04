import { expect, test } from "bun:test";
import { legalMoves, type Move } from "./engine";
import { type Game, load, play, save, start } from "./file";
import { generate, random } from "./generate";

function playOn(
	game: Game,
	seed: number,
	max = Number.POSITIVE_INFINITY,
): Game {
	const rand = random(seed);
	let g = game;
	for (let i = 0; i < max && !g.state.over; i++) {
		const moves = legalMoves(g.state);
		const next = play(g, moves[Math.floor(rand() * moves.length)] as Move);
		if (typeof next === "string") throw new Error(next);
		g = next;
	}
	return g;
}

test("a game saved mid-way loads to the same state and plays on to the same result", () => {
	const mid = playOn(start(generate(7), 7, 1), 99, 30);
	const text = save(mid);
	const back = load(text);
	expect(back).toEqual(mid);
	expect(save(back)).toBe(text);
	expect(playOn(back, 5)).toEqual(playOn(mid, 5));
});

test("the file is readable JSON with the seed, tile codes, moves, and snapshot", () => {
	const g = playOn(start(generate(3), 3), 1, 2);
	const file = JSON.parse(save(g));
	expect(file.format).toBe("tile-laying-game/1");
	expect(file.seed).toBe(3);
	expect(file.tiles[0]).toBe("CRFR");
	expect(file.moves).toHaveLength(2);
	expect(file.state.board).toHaveLength(3);
});

test("a hand-written file with no moves loads at the position it describes", () => {
	const text = JSON.stringify({
		format: "tile-laying-game/1",
		seed: null,
		tiles: ["CRFR", "FRRR+J", "FRRR+J"],
		starter: 0,
		moves: [],
		state: {
			board: [{ x: 0, y: 0, r: 0, code: "CRFR" }],
			meeples: [{ x: 0, y: 0, feature: "road0", player: 1 }],
			scores: [4, 2],
			hands: ["FRRR+J", "FRRR+J"],
		},
	});
	const g = load(text);
	expect(g.state.scores).toEqual([4, 2]);
	expect(g.state.turn).toBe(0);
	// Both ends of player 2's road get junctions; the second one finishes and scores it.
	const one = play(g, { x: 1, y: 0, r: 0, meeple: null });
	if (typeof one === "string") throw new Error(one);
	const two = play(one, { x: -1, y: 0, r: 0, meeple: null });
	if (typeof two === "string") throw new Error(two);
	expect(two.state.over).toBe(true);
	expect(two.state.scores).toEqual([4, 5]);
});

test("loading rejects files that don't add up", () => {
	const g = playOn(start(generate(11), 11), 2, 5);
	const file = JSON.parse(save(g));
	expect(() =>
		load(
			JSON.stringify({ ...file, state: { ...file.state, scores: [99, 0] } }),
		),
	).toThrow("replaying the moves doesn't give the saved state");
	expect(() =>
		load(
			JSON.stringify({
				...file,
				moves: [{ x: 50, y: 50, r: 0, meeple: null }],
			}),
		),
	).toThrow("move 1 is illegal");
	expect(() => load("{}")).toThrow("not a tile-laying-game/1 game file");
	expect(() => load("nope")).toThrow("not a JSON file");
	const bad = {
		...file,
		moves: [],
		state: { ...file.state, board: [{ x: 0, y: 0, r: 0, code: "FFFR" }] },
	};
	expect(() => load(JSON.stringify(bad))).toThrow(
		"the snapshot is not a valid position",
	);
});
