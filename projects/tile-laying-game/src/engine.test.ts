import { expect, test } from "bun:test";
import {
	apply,
	legalMoves,
	MEEPLES,
	type Meeple,
	type Move,
	newGame,
	type Placed,
	type State,
	winner,
} from "./engine";
import { generate, random } from "./generate";

const tile = (code: string, x: number, y: number, r = 0): Placed => ({
	x,
	y,
	r,
	code,
});
const meeple = (
	player: 0 | 1,
	x: number,
	y: number,
	feature: string,
): Meeple => ({ x, y, feature, player });

/** A position by hand. The filler deck keeps the game going so only the move under test scores. */
function position(
	board: Placed[],
	hands: State["hands"],
	more: Partial<State> = {},
): State {
	return {
		board,
		meeples: [],
		scores: [0, 0],
		hands,
		deck: ["FRFR", "FRFR", "FRFR"],
		discards: [],
		turn: 0,
		starter: 0,
		over: false,
		...more,
	};
}

function play(state: State, ...moves: Move[]): State {
	let s = state;
	for (const m of moves) {
		const next = apply(s, m);
		if (typeof next === "string") throw new Error(next);
		s = next;
	}
	return s;
}

const move = (
	x: number,
	y: number,
	r = 0,
	meeple: string | null = null,
): Move => ({ x, y, r, meeple });

test("a new game deals the starter's tile first and both hands are visible", () => {
	const s = newGame(["CRFR", "FRFR", "CFFF", "FFRR"], 1);
	expect(s.turn).toBe(1);
	expect(s.hands).toEqual(["CFFF", "FRFR"]);
	expect(s.deck).toEqual(["FFRR"]);
});

test("a finished road scores 1 per tile and its meeple comes home", () => {
	let s = position([tile("CRFR", 0, 0)], ["FRRR+J", "FRRR+J"]);
	s = play(s, move(1, 0, 0, "road2")); // the junction's west road joins the start tile's road
	expect(s.meeples).toHaveLength(1);
	expect(s.hands[0]).toBe("FRFR"); // drawn at the end of the turn
	s = play(s, move(-1, 0)); // a junction on the other end finishes it
	expect(s.scores).toEqual([3, 0]);
	expect(s.meeples).toEqual([]);
});

test("a finished city scores 2 per tile and per shield", () => {
	let s = position([tile("CFCF+S", 0, 0)], ["CFFF", "CFFF"]);
	s = play(s, move(0, -1, 2, "city0"), move(0, 1));
	expect(s.scores).toEqual([8, 0]);
});

test("tied meeples on a joined city both score in full", () => {
	const s = position(
		[tile("CFFF", 0, 0), tile("CFFF", 0, -2, 2)],
		["CFCF", "FRFR"],
		{
			meeples: [meeple(0, 0, 0, "city0"), meeple(1, 0, -2, "city0")],
		},
	);
	expect(play(s, move(0, -1)).scores).toEqual([6, 6]);
});

test("the player with more meeples on a feature takes all of it", () => {
	const s = position(
		[tile("CFFF", 0, 0), tile("CFFF", 0, -2, 2), tile("CFFF", 1, -1, 3)],
		["CCCF", "FRFR"],
		{
			meeples: [
				meeple(0, 0, 0, "city0"),
				meeple(1, 0, -2, "city0"),
				meeple(0, 1, -1, "city0"),
			],
		},
	);
	const after = play(s, move(0, -1));
	expect(after.scores).toEqual([8, 0]);
	expect(after.meeples).toEqual([]);
});

test("a surrounded monastery scores 9", () => {
	const ring = [
		[-1, -1],
		[0, -1],
		[1, -1],
		[-1, 0],
		[1, 0],
		[-1, 1],
		[0, 1],
	].map(([x, y]) => tile("FFFF+M", x as number, y as number));
	const s = position([tile("FFFF+M", 0, 0), ...ring], ["FFFF+M", "FFFF+M"], {
		meeples: [meeple(0, 0, 0, "monastery")],
	});
	const after = play(s, move(1, 1));
	expect(after.scores).toEqual([9, 0]);
	expect(after.meeples).toEqual([]);
});

test("a meeple can't go on a feature that already has one, counting the tiles it joins", () => {
	const s = position([tile("CRFR", 0, 0)], ["FRRR+J", "FRFR"], {
		meeples: [meeple(1, 0, 0, "road0")],
	});
	expect(apply(s, move(1, 0, 0, "road2"))).toBe(
		"that feature already has a meeple",
	);
	expect(
		legalMoves(s).some(
			(m) => m.x === 1 && m.y === 0 && m.r === 0 && m.meeple === "road2",
		),
	).toBe(false);
	expect(
		legalMoves(s).some(
			(m) => m.x === 1 && m.y === 0 && m.r === 0 && m.meeple === "road0",
		),
	).toBe(true);
});

test("illegal placements say why", () => {
	const s = position([tile("CRFR", 0, 0)], ["CFFF", "FRFR"]);
	expect(apply(s, move(0, 0))).toBe("that spot already has a tile");
	expect(apply(s, move(5, 5))).toBe(
		"the tile must touch a placed tile, with every touching edge matching",
	);
	expect(apply(s, move(0, 1))).toBe(
		"the tile must touch a placed tile, with every touching edge matching",
	); // city onto field
	expect(apply(s, move(0, 1, 2))).not.toBeTypeOf("string"); // turned, its field meets the field
	expect(apply(s, move(0, -1, 2, "road0"))).toBe(
		"the tile has no feature road0",
	);
	const out = position([tile("CRFR", 0, 0)], ["CFFF", "FRFR"], {
		meeples: Array.from({ length: MEEPLES }, () => meeple(0, 0, 0, "field1")),
	});
	expect(apply(out, move(0, -1, 2, "city0"))).toBe("no meeples left");
	expect(apply({ ...s, over: true }, move(0, -1, 2))).toBe("the game is over");
});

test("a tile with no legal placement is set aside and another drawn", () => {
	const s = newGame(["FFFF+M", "CCCC", "FFFF+M", "FFFF+M"], 0);
	expect(s.discards).toEqual(["CCCC"]);
	expect(s.hands).toEqual(["FFFF+M", "FFFF+M"]);
	expect(s.deck).toEqual([]);
});

test("at the end, unfinished roads, cities, and monasteries score 1 per tile and shield", () => {
	const s = position(
		[tile("CRFR", 0, 0), tile("FRFR", 1, 0)],
		["FFFF+M", null],
		{
			deck: [],
			meeples: [meeple(0, 0, 0, "road0"), meeple(1, 0, 0, "city0")],
		},
	);
	const end = play(s, move(0, 1, 0, "monastery"));
	expect(end.over).toBe(true);
	// Road: 2 tiles. Monastery: itself and its 2 neighbours. City: 1 tile.
	expect(end.scores).toEqual([5, 1]);
	expect(end.meeples).toEqual([]);
	expect(winner(end)).toBe(0);
});

test("at the end, a field scores 3 per finished city it touches, each city once", () => {
	const s = position(
		[tile("CFFF", 0, 0), tile("CFFF", 0, -1, 2)],
		["CFFF", null],
		{
			deck: [],
			meeples: [meeple(0, 0, 0, "field0"), meeple(1, 0, -1, "field0")],
		},
	);
	// The new tile's field joins the farmer's field and adds an unfinished city, which doesn't count.
	const end = play(s, move(1, 0, 0));
	expect(end.scores).toEqual([3, 3]); // the field above the city touches it too
});

test("on a tie the starting player loses", () => {
	const s = position([tile("CRFR", 0, 0)], [null, null], {
		over: true,
		scores: [10, 10],
		starter: 1,
	});
	expect(winner(s)).toBe(0);
	expect(winner({ ...s, starter: 0 })).toBe(1);
	expect(winner({ ...s, over: false })).toBeNull();
});

/** Plays a whole game with random legal moves, checking the rules hold after every move. */
function randomGame(seed: number): State {
	const tiles = generate(seed);
	const rand = random(seed);
	let s = newGame(tiles, (seed % 2) as 0 | 1);
	while (!s.over) {
		const moves = legalMoves(s);
		expect(moves.length).toBeGreaterThan(0);
		const before = s.scores;
		s = play(s, moves[Math.floor(rand() * moves.length)] as Move);
		expect(s.scores[0]).toBeGreaterThanOrEqual(before[0]);
		expect(s.scores[1]).toBeGreaterThanOrEqual(before[1]);
		for (const p of [0, 1])
			expect(
				s.meeples.filter((m) => m.player === p).length,
			).toBeLessThanOrEqual(MEEPLES);
	}
	expect(s.board.length + s.discards.length).toBe(tiles.length);
	expect(s.meeples).toEqual([]);
	return s;
}

test("whole random games keep the rules and are deterministic", () => {
	for (const seed of [1, 2, 3])
		expect(randomGame(seed)).toEqual(randomGame(seed));
});
