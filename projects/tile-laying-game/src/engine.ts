// The rules engine: pure functions over a plain JSON game state. Nothing else changes game state.
import {
	analyse,
	edgeAt,
	type Features,
	features,
	rotatePort,
	type Side,
} from "./tiles";

export type Player = 0 | 1;
export const MEEPLES = 7;

/** A feature of one tile, in the tile's own (unrotated) numbering: "city0", "road1", "field2", or "monastery". */
export type FeatureRef = string;

export interface Placed {
	x: number;
	y: number;
	r: number; // quarter turns clockwise
	code: string;
}

export interface Meeple {
	x: number;
	y: number;
	feature: FeatureRef;
	player: Player;
}

export interface State {
	board: Placed[]; // in the order they were placed; the first is the start tile
	meeples: Meeple[];
	scores: [number, number];
	hands: [string | null, string | null]; // each player's next tile, visible to both
	deck: string[]; // tiles left to draw, in order
	discards: string[]; // tiles set aside because they had no legal placement
	turn: Player;
	starter: Player;
	over: boolean;
}

export interface Move {
	x: number;
	y: number;
	r: number;
	meeple: FeatureRef | null;
}

const STEP: [number, number][] = [
	[0, -1],
	[1, 0],
	[0, 1],
	[-1, 0],
];

const key = (x: number, y: number) => `${x},${y}`;

/** A new game from a tile set (start tile first, then the draw order); the starter draws first. */
export function newGame(tiles: string[], starter: Player = 0): State {
	const [start, ...deck] = tiles;
	if (!start) throw new Error("a tile set needs a start tile");
	for (const t of tiles) features(t);
	const state: State = {
		board: [{ x: 0, y: 0, r: 0, code: start }],
		meeples: [],
		scores: [0, 0],
		hands: [null, null],
		deck,
		discards: [],
		turn: starter,
		starter,
		over: false,
	};
	state.hands[starter] = state.deck.shift() ?? null;
	state.hands[other(starter)] = state.deck.shift() ?? null;
	return settle(state);
}

const other = (p: Player): Player => (p === 0 ? 1 : 0);

function tileMap(board: Placed[]): Map<string, Placed> {
	return new Map(board.map((t) => [key(t.x, t.y), t]));
}

/** Can `code`, turned `r`, go at (x, y)? Needs an empty cell, a neighbour, and every touching edge matching. */
function fits(
	map: Map<string, Placed>,
	code: string,
	x: number,
	y: number,
	r: number,
): boolean {
	if (map.has(key(x, y))) return false;
	let touching = 0;
	for (let side = 0; side < 4; side++) {
		const [dx, dy] = STEP[side] as [number, number];
		const n = map.get(key(x + dx, y + dy));
		if (!n) continue;
		touching++;
		if (
			edgeAt(code, r, side as Side) !==
			edgeAt(n.code, n.r, ((side + 2) % 4) as Side)
		)
			return false;
	}
	return touching > 0;
}

/** Every spot and rotation where the current tile can go. */
export function placements(
	state: State,
): { x: number; y: number; r: number }[] {
	const code = state.hands[state.turn];
	if (state.over || !code) return [];
	return placementsFor(state.board, code);
}

function placementsFor(
	board: Placed[],
	code: string,
): { x: number; y: number; r: number }[] {
	const map = tileMap(board);
	const spots = new Map<string, [number, number]>();
	for (const t of board)
		for (const [dx, dy] of STEP)
			if (!map.has(key(t.x + dx, t.y + dy)))
				spots.set(key(t.x + dx, t.y + dy), [t.x + dx, t.y + dy]);
	const out: { x: number; y: number; r: number }[] = [];
	const sorted = [...spots.values()].sort((a, b) => a[1] - b[1] || a[0] - b[0]);
	// Rotations that give the same tile (a symmetric tile) are listed once.
	const seen = new Set<string>();
	const turns = [0, 1, 2, 3].filter((r) => {
		const k = [0, 1, 2, 3].map((s) => edgeAt(code, r, s as Side)).join("");
		if (seen.has(k)) return false;
		seen.add(k);
		return true;
	});
	for (const [x, y] of sorted)
		for (const r of turns) if (fits(map, code, x, y, r)) out.push({ x, y, r });
	return out;
}

const refs = (f: Features): FeatureRef[] => [
	...f.cities.map((_, i) => `city${i}`),
	...f.roads.map((_, i) => `road${i}`),
	...f.fields.map((_, i) => `field${i}`),
	...(f.monastery ? ["monastery"] : []),
];

// The board as connected features: a node per (tile, feature), joined across matching edges.
interface Node {
	tile: number;
	ref: FeatureRef;
}

interface Group {
	kind: "city" | "road" | "field" | "monastery";
	nodes: number[];
	tiles: Set<number>;
	shields: number;
	open: number; // city or road edges with no tile beyond them
	meeples: Meeple[];
	cities: Set<number>; // for fields: the root of each city it touches
}

interface Analysis {
	nodes: Node[];
	root: (n: number) => number;
	groups: Map<number, Group>;
	nodeOf: (tile: number, ref: FeatureRef) => number;
}

function analyseBoard(board: Placed[], meeples: Meeple[]): Analysis {
	const map = tileMap(board);
	const index = new Map(board.map((t, i) => [key(t.x, t.y), i]));
	const nodes: Node[] = [];
	const ids = new Map<string, number>();
	for (const [i, t] of board.entries())
		for (const ref of refs(features(t.code))) {
			ids.set(`${i}:${ref}`, nodes.length);
			nodes.push({ tile: i, ref });
		}
	const nodeOf = (tile: number, ref: FeatureRef) => {
		const n = ids.get(`${tile}:${ref}`);
		if (n === undefined) throw new Error(`no feature ${ref} on tile ${tile}`);
		return n;
	};
	const parent = nodes.map((_, i) => i);
	const root = (n: number): number => {
		let r = n;
		while (parent[r] !== r) r = parent[r] as number;
		while (parent[n] !== r) {
			const next = parent[n] as number;
			parent[n] = r;
			n = next;
		}
		return r;
	};
	const union = (a: number, b: number) => {
		const ra = root(a);
		const rb = root(b);
		if (ra !== rb) parent[Math.max(ra, rb)] = Math.min(ra, rb);
	};

	// Which feature of a placed tile meets a world side or world port.
	const onSide = (
		t: Placed,
		kind: "city" | "road",
		side: number,
	): FeatureRef | null => {
		const local = (side - t.r + 8) % 4;
		const list =
			kind === "city" ? features(t.code).cities : features(t.code).roads;
		const i = list.findIndex((f) => f.sides.includes(local as Side));
		return i < 0 ? null : `${kind}${i}`;
	};
	const onPort = (t: Placed, port: number): FeatureRef | null => {
		const local = rotatePort(port, 4 - (t.r % 4));
		const i = features(t.code).fields.findIndex((f) => f.ports.includes(local));
		return i < 0 ? null : `field${i}`;
	};

	const open = new Map<number, number>();
	for (const [i, t] of board.entries()) {
		for (let side = 0; side < 4; side++) {
			const [dx, dy] = STEP[side] as [number, number];
			const j = index.get(key(t.x + dx, t.y + dy));
			for (const kind of ["city", "road"] as const) {
				const mine = onSide(t, kind, side);
				if (!mine) continue;
				if (j === undefined) {
					const n = nodeOf(i, mine);
					open.set(n, (open.get(n) ?? 0) + 1);
					continue;
				}
				const theirs = onSide(board[j] as Placed, kind, (side + 2) % 4);
				if (theirs) union(nodeOf(i, mine), nodeOf(j, theirs));
			}
			if (j === undefined) continue;
			for (let k = 0; k < 3; k++) {
				const mine = onPort(t, side * 3 + k);
				const theirs = onPort(
					board[j] as Placed,
					((side + 2) % 4) * 3 + (2 - k),
				);
				if (mine && theirs) union(nodeOf(i, mine), nodeOf(j, theirs));
			}
		}
	}

	const groups = new Map<number, Group>();
	for (const [n, node] of nodes.entries()) {
		const r = root(n);
		const kind = node.ref.replace(/\d+$/, "") as Group["kind"];
		let g = groups.get(r);
		if (!g) {
			g = {
				kind,
				nodes: [],
				tiles: new Set(),
				shields: 0,
				open: 0,
				meeples: [],
				cities: new Set(),
			};
			groups.set(r, g);
		}
		g.nodes.push(n);
		g.tiles.add(node.tile);
		g.open += open.get(n) ?? 0;
		const t = board[node.tile] as Placed;
		const f = features(t.code);
		if (kind === "city" && f.cities[Number(node.ref.slice(4))]?.shield)
			g.shields++;
		if (kind === "monastery") {
			let around = 0;
			for (let dx = -1; dx <= 1; dx++)
				for (let dy = -1; dy <= 1; dy++)
					if ((dx || dy) && map.has(key(t.x + dx, t.y + dy))) around++;
			g.open = 8 - around;
		}
	}
	// Field to city links, once every city has its root.
	for (const [n, node] of nodes.entries()) {
		if (!node.ref.startsWith("field")) continue;
		const field = features((board[node.tile] as Placed).code).fields[
			Number(node.ref.slice(5))
		];
		for (const c of field?.cities ?? [])
			groups.get(root(n))?.cities.add(root(nodeOf(node.tile, `city${c}`)));
	}
	for (const m of meeples) {
		const i = index.get(key(m.x, m.y));
		if (i === undefined)
			throw new Error(`meeple at ${m.x},${m.y} is not on a tile`);
		groups.get(root(nodeOf(i, m.feature)))?.meeples.push(m);
	}
	return { nodes, root, groups, nodeOf };
}

const complete = (g: Group) => g.open === 0;

/** Points a feature is worth, finished (during play) or not (at the end). */
function points(g: Group, a: Analysis, finished: boolean): number {
	switch (g.kind) {
		case "road":
			return g.tiles.size;
		case "city":
			return finished
				? 2 * (g.tiles.size + g.shields)
				: g.tiles.size + g.shields;
		case "monastery":
			return 9 - g.open;
		case "field":
			return (
				3 *
				[...g.cities].filter((c) => complete(a.groups.get(c) as Group)).length
			);
	}
}

/** The players with the most meeples on a feature; tied players all score. */
function majority(meeples: Meeple[]): Player[] {
	const count = [0, 0];
	for (const m of meeples) count[m.player] = (count[m.player] as number) + 1;
	const top = Math.max(...count);
	return top === 0 ? [] : ([0, 1] as Player[]).filter((p) => count[p] === top);
}

export const meeplesLeft = (state: State, p: Player): number =>
	MEEPLES - state.meeples.filter((m) => m.player === p).length;

/** Features of the current tile, placed as given, where a meeple may go: empty after joining the board. */
export function meepleSpots(
	state: State,
	at: { x: number; y: number; r: number },
): FeatureRef[] {
	const code = state.hands[state.turn];
	if (!code || meeplesLeft(state, state.turn) === 0) return [];
	const board = [...state.board, { ...at, code }];
	const a = analyseBoard(board, state.meeples);
	const i = board.length - 1;
	return refs(features(code)).filter(
		(ref) =>
			(a.groups.get(a.root(a.nodeOf(i, ref))) as Group).meeples.length === 0,
	);
}

/** Every legal move for the current player. */
export function legalMoves(state: State): Move[] {
	return placements(state).flatMap((p) => [
		{ ...p, meeple: null },
		...meepleSpots(state, p).map((m) => ({ ...p, meeple: m })),
	]);
}

/** The next state after `move`, or the reason the move is illegal. Never changes `state`. */
export function apply(state: State, move: Move): State | string {
	if (state.over) return "the game is over";
	const code = state.hands[state.turn];
	if (!code) return "no tile to place";
	const map = tileMap(state.board);
	const r = ((move.r % 4) + 4) % 4;
	if (
		!Number.isInteger(move.x) ||
		!Number.isInteger(move.y) ||
		!Number.isInteger(move.r)
	)
		return "the spot and rotation must be whole numbers";
	if (map.has(key(move.x, move.y))) return "that spot already has a tile";
	if (!fits(map, code, move.x, move.y, r))
		return "the tile must touch a placed tile, with every touching edge matching";
	const at = { x: move.x, y: move.y, r };
	if (move.meeple !== null) {
		if (!refs(features(code)).includes(move.meeple))
			return `the tile has no feature ${move.meeple}`;
		if (meeplesLeft(state, state.turn) === 0) return "no meeples left";
		if (!meepleSpots(state, at).includes(move.meeple))
			return "that feature already has a meeple";
	}
	const next: State = structuredClone(state);
	next.board.push({ ...at, code });
	if (move.meeple !== null)
		next.meeples.push({
			x: at.x,
			y: at.y,
			feature: move.meeple,
			player: state.turn,
		});
	scoreFinished(next, at);
	next.hands[state.turn] = next.deck.shift() ?? null;
	next.turn = other(state.turn);
	return settle(next);
}

/** Score and clear the roads, cities, and monasteries the new tile finished. */
function scoreFinished(state: State, at: { x: number; y: number }) {
	const a = analyseBoard(state.board, state.meeples);
	const near = new Set(
		state.board.flatMap((t, i) =>
			Math.abs(t.x - at.x) <= 1 && Math.abs(t.y - at.y) <= 1 ? [i] : [],
		),
	);
	const placed = state.board.length - 1;
	const done = new Set<Meeple>();
	for (const g of a.groups.values()) {
		if (g.kind === "field" || !complete(g)) continue;
		const touched =
			g.kind === "monastery"
				? [...g.tiles].some((t) => near.has(t))
				: g.tiles.has(placed);
		if (!touched) continue;
		for (const p of majority(g.meeples)) state.scores[p] += points(g, a, true);
		for (const m of g.meeples) done.add(m);
	}
	state.meeples = state.meeples.filter((m) => !done.has(m));
}

/**
 * Bring the state to a point where the current player can move, or the game is over:
 * set aside tiles with no legal placement (drawing another), skip a player with no tile, and score the end.
 */
function settle(state: State): State {
	for (;;) {
		if (state.hands[0] === null && state.hands[1] === null) {
			finalScore(state);
			return state;
		}
		const code = state.hands[state.turn];
		if (code === null) {
			state.turn = other(state.turn);
			continue;
		}
		if (placementsFor(state.board, code).length === 0) {
			state.discards.push(code);
			state.hands[state.turn] = state.deck.shift() ?? null;
			continue;
		}
		return state;
	}
}

function finalScore(state: State) {
	const a = analyseBoard(state.board, state.meeples);
	for (const g of a.groups.values()) {
		if (!g.meeples.length) continue;
		for (const p of majority(g.meeples))
			state.scores[p] += points(g, a, g.kind === "field" ? false : complete(g));
	}
	state.meeples = [];
	state.over = true;
}

/** The winner of a finished game: the higher score, and on a tie the player who did not start. */
export function winner(state: State): Player | null {
	if (!state.over) return null;
	const [a, b] = state.scores;
	if (a !== b) return a > b ? 0 : 1;
	return other(state.starter);
}

/** Where on the board a meeple stands, in board units, for drawing. */
export function meeplePoint(m: Meeple, board: Placed[]): [number, number] {
	const t = board.find((b) => b.x === m.x && b.y === m.y);
	if (!t) throw new Error(`meeple at ${m.x},${m.y} is not on a tile`);
	return anchorPoint(t, m.feature);
}

export function anchorPoint(t: Placed, ref: FeatureRef): [number, number] {
	const f = features(t.code);
	const kind = ref.replace(/\d+$/, "");
	const i = Number(ref.slice(kind.length));
	const p =
		kind === "city"
			? f.cities[i]?.anchor
			: kind === "road"
				? f.roads[i]?.anchor
				: kind === "field"
					? f.fields[i]?.anchor
					: f.monastery?.anchor;
	if (!p) throw new Error(`no feature ${ref} on ${t.code}`);
	let [x, y] = p;
	for (let k = 0; k < t.r % 4; k++) [x, y] = [1 - y, x];
	return [t.x + x, t.y + y];
}

/** A reason a hand-written state is not usable, or null. */
export function checkState(state: State): string | null {
	const map = new Map<string, Placed>();
	for (const t of state.board) {
		if (typeof analyse(t.code) === "string") return `bad tile ${t.code}`;
		if (map.has(key(t.x, t.y))) return `two tiles at ${t.x},${t.y}`;
		if (map.size && !fits(map, t.code, t.x, t.y, t.r))
			return `tile at ${t.x},${t.y} doesn't fit`;
		map.set(key(t.x, t.y), t);
	}
	for (const t of [...state.deck, ...state.hands.filter((h) => h !== null)])
		if (typeof analyse(t) === "string") return `bad tile ${t}`;
	for (const p of [0, 1] as Player[])
		if (meeplesLeft(state, p) < 0)
			return `player ${p + 1} has more than ${MEEPLES} meeples out`;
	try {
		analyseBoard(state.board, state.meeples);
	} catch (e) {
		return (e as Error).message;
	}
	return null;
}
