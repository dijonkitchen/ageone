/**
 * Monte Carlo tree search over whole turns: a node's move is both stones of
 * a turn (one on Black's opening), so the tree alternates players cleanly.
 *
 * Search runs on a flat board that tracks, for every window of six cells, how
 * many stones each colour has in it. That makes the tactics cheap:
 *   - a win this turn is a window with no opponent stones and at most
 *     `required` empty cells;
 *   - an opponent threat is a window the opponent could fill on its next
 *     turn (no own stones, at most two empty cells), which must be blocked.
 * Moves are generated from the best-scoring cells near existing stones, and
 * rollouts play a few turns of a noisy greedy policy, then score the board.
 * Everything is driven by the injected `rng`, so a seed gives the same games.
 */

import { requiredStones } from "../game.js";
import type { GameState, Move, Player } from "../types.js";
import { WIN_LENGTH } from "../types.js";
import type { Agent, Rng } from "./agent.js";
import { mulberry32 } from "./random.js";

const BLACK = 1;
const WHITE = 2;
type Colour = 1 | 2;
const other = (c: Colour): Colour => (c === BLACK ? WHITE : BLACK);
const colourOf = (p: Player): Colour => (p === "black" ? BLACK : WHITE);

/** Window weights by stone count; a window of five or six is decisive. */
const WEIGHT = [0, 1, 6, 30, 200, 1000, 100_000];
const AXES: ReadonlyArray<readonly [number, number]> = [
	[0, 1],
	[1, 0],
	[1, 1],
	[1, -1],
];

interface Geometry {
	/** windows[w * 6 + k] is the k-th cell of window w. */
	readonly windows: Int32Array;
	readonly count: number;
	/** Windows through each cell. */
	readonly cellWindows: ReadonlyArray<Int32Array>;
	/** Cells within distance 2 of each cell, for candidate generation. */
	readonly near: ReadonlyArray<Int32Array>;
}

const geometries = new Map<number, Geometry>();

const geometry = (size: number): Geometry => {
	const cached = geometries.get(size);
	if (cached) return cached;
	const flat: number[] = [];
	const through: number[][] = Array.from({ length: size * size }, () => []);
	for (let r = 0; r < size; r += 1) {
		for (let c = 0; c < size; c += 1) {
			for (const [dr, dc] of AXES) {
				const er = r + dr * (WIN_LENGTH - 1);
				const ec = c + dc * (WIN_LENGTH - 1);
				if (er < 0 || er >= size || ec < 0 || ec >= size) continue;
				const w = flat.length / WIN_LENGTH;
				for (let k = 0; k < WIN_LENGTH; k += 1) {
					const cell = (r + dr * k) * size + (c + dc * k);
					flat.push(cell);
					through[cell]?.push(w);
				}
			}
		}
	}
	const near = Array.from({ length: size * size }, (_, i) => {
		const r = Math.floor(i / size);
		const c = i % size;
		const out: number[] = [];
		for (let dr = -2; dr <= 2; dr += 1) {
			for (let dc = -2; dc <= 2; dc += 1) {
				const nr = r + dr;
				const nc = c + dc;
				if ((dr || dc) && nr >= 0 && nr < size && nc >= 0 && nc < size) {
					out.push(nr * size + nc);
				}
			}
		}
		return Int32Array.from(out);
	});
	const g: Geometry = {
		windows: Int32Array.from(flat),
		count: flat.length / WIN_LENGTH,
		cellWindows: through.map((ws) => Int32Array.from(ws)),
		near,
	};
	geometries.set(size, g);
	return g;
};

/** A mutable board with per-window stone counts, private to the search. */
class SearchBoard {
	readonly cells: Int8Array;
	/** counts[colour][window]; index 0 is unused. */
	readonly counts: [Int16Array, Int16Array, Int16Array];
	stones: number;

	constructor(
		readonly size: number,
		readonly geo: Geometry,
		cells?: Int8Array,
		counts?: [Int16Array, Int16Array, Int16Array],
		stones = 0,
	) {
		this.cells = cells ?? new Int8Array(size * size);
		this.counts = counts ?? [
			new Int16Array(0),
			new Int16Array(geo.count),
			new Int16Array(geo.count),
		];
		this.stones = stones;
	}

	static from(state: GameState): SearchBoard {
		const b = new SearchBoard(state.size, geometry(state.size));
		state.board.forEach((row, r) => {
			row.forEach((cell, c) => {
				if (cell) b.place(r * state.size + c, colourOf(cell));
			});
		});
		return b;
	}

	clone(): SearchBoard {
		return new SearchBoard(
			this.size,
			this.geo,
			this.cells.slice(),
			[this.counts[0], this.counts[BLACK].slice(), this.counts[WHITE].slice()],
			this.stones,
		);
	}

	/** Places a stone; returns true if it completes six or more in a row. */
	place(cell: number, colour: Colour): boolean {
		this.cells[cell] = colour;
		this.stones += 1;
		const mine = this.counts[colour];
		let won = false;
		for (const w of this.geo.cellWindows[cell] ?? []) {
			const n = (mine[w] ?? 0) + 1;
			mine[w] = n;
			if (n === WIN_LENGTH) won = true;
		}
		return won;
	}

	isFull(): boolean {
		return this.stones >= this.cells.length;
	}

	windowCells(w: number): Int32Array {
		return this.geo.windows.subarray(w * WIN_LENGTH, (w + 1) * WIN_LENGTH);
	}

	/** Empty cells completing a window `colour` can fill with `stones` stones. */
	winningCells(colour: Colour, stones: number): number[] | null {
		const mine = this.counts[colour];
		const theirs = this.counts[other(colour)];
		for (let w = 0; w < this.geo.count; w += 1) {
			if ((theirs[w] ?? 0) === 0 && (mine[w] ?? 0) >= WIN_LENGTH - stones) {
				return [...this.windowCells(w)].filter((c) => this.cells[c] === 0);
			}
		}
		return null;
	}

	/** Windows `attacker` could fill with two stones on its next turn. */
	threats(attacker: Colour): number[] {
		const mine = this.counts[attacker];
		const theirs = this.counts[other(attacker)];
		const out: number[] = [];
		for (let w = 0; w < this.geo.count; w += 1) {
			if ((theirs[w] ?? 0) === 0 && (mine[w] ?? 0) >= WIN_LENGTH - 2) {
				out.push(w);
			}
		}
		return out;
	}

	/** Value of a stone for `colour` at an empty cell: attack plus defence. */
	cellScore(cell: number, colour: Colour): number {
		const mine = this.counts[colour];
		const theirs = this.counts[other(colour)];
		let score = 0;
		for (const w of this.geo.cellWindows[cell] ?? []) {
			const m = mine[w] ?? 0;
			const t = theirs[w] ?? 0;
			if (t === 0) score += (WEIGHT[m + 1] ?? 0) - (WEIGHT[m] ?? 0);
			if (m === 0) score += 0.8 * ((WEIGHT[t + 1] ?? 0) - (WEIGHT[t] ?? 0));
		}
		return score;
	}

	/** Empty cells near any stone, or the centre on an empty board. */
	candidates(): number[] {
		if (this.stones === 0) {
			const mid = Math.floor(this.size / 2);
			return [mid * this.size + mid];
		}
		const seen = new Uint8Array(this.cells.length);
		const out: number[] = [];
		for (let i = 0; i < this.cells.length; i += 1) {
			if (this.cells[i] === 0) continue;
			for (const n of this.geo.near[i] ?? []) {
				if (this.cells[n] === 0 && !seen[n]) {
					seen[n] = 1;
					out.push(n);
				}
			}
		}
		if (out.length === 0) {
			for (let i = 0; i < this.cells.length; i += 1) {
				if (this.cells[i] === 0) out.push(i);
			}
		}
		return out;
	}

	/** Board value for `colour`, from window potentials on both sides. */
	evaluate(colour: Colour): number {
		const mine = this.counts[colour];
		const theirs = this.counts[other(colour)];
		let v = 0;
		for (let w = 0; w < this.geo.count; w += 1) {
			const m = mine[w] ?? 0;
			const t = theirs[w] ?? 0;
			if (t === 0) v += WEIGHT[m] ?? 0;
			if (m === 0) v -= WEIGHT[t] ?? 0;
		}
		return v;
	}
}

const ranked = (b: SearchBoard, colour: Colour, cells: number[]): number[] =>
	cells
		.map((c) => ({ c, s: b.cellScore(c, colour) }))
		.sort((x, y) => y.s - x.s)
		.map((x) => x.c);

/**
 * Candidate turns for `colour`, best first. A win this turn is the only move;
 * otherwise every move must block all of the opponent's next-turn threats
 * when it can.
 */
const generateMoves = (
	b: SearchBoard,
	colour: Colour,
	required: number,
	width: number,
): number[][] => {
	const win = b.winningCells(colour, required);
	if (win) {
		const pad = ranked(b, colour, b.candidates()).filter(
			(c) => !win.includes(c),
		);
		return [[...win, ...pad].slice(0, required)];
	}
	const top = ranked(b, colour, b.candidates()).slice(0, width);
	const threats = b.threats(other(colour));
	if (threats.length > 0) {
		const blockers = ranked(
			b,
			colour,
			[...new Set(threats.flatMap((w) => [...b.windowCells(w)]))].filter(
				(c) => b.cells[c] === 0,
			),
		).slice(0, width);
		const covers = (cells: number[]): number =>
			threats.filter((w) => cells.some((c) => b.windowCells(w).includes(c)))
				.length;
		const options: number[][] = [];
		for (const a of blockers) {
			if (required === 1) options.push([a]);
			else {
				for (const c of [...blockers, ...top]) {
					if (c !== a) options.push([a, c]);
				}
			}
		}
		const best = Math.max(...options.map(covers));
		const seen = new Set<string>();
		return options
			.filter((m) => covers(m) === best)
			.filter((m) => {
				const key = [...m].sort((x, y) => x - y).join(",");
				if (seen.has(key)) return false;
				seen.add(key);
				return true;
			})
			.slice(0, width * 2);
	}
	if (required === 1) return top.map((c) => [c]);
	const pairs: number[][] = [];
	for (let i = 0; i < top.length; i += 1) {
		for (let j = i + 1; j < top.length; j += 1) {
			const a = top[i];
			const c = top[j];
			if (a !== undefined && c !== undefined) pairs.push([a, c]);
		}
	}
	return pairs.slice(0, width * 2);
};

interface Node {
	readonly move: number[] | null;
	/** Colour that played `move` into this node. */
	readonly mover: Colour;
	readonly parent: Node | null;
	readonly children: Node[];
	untried: number[][] | null;
	visits: number;
	/** Total value for `mover`, each playout in [0, 1]. */
	value: number;
	/** Set when `move` won the game. */
	readonly terminal: boolean;
}

const newNode = (
	move: number[] | null,
	mover: Colour,
	parent: Node | null,
	terminal: boolean,
): Node => ({
	move,
	mover,
	parent,
	children: [],
	untried: null,
	visits: 0,
	value: 0,
	terminal,
});

export interface MctsOptions {
	/** Playouts per turn. */
	readonly iterations?: number;
	/** Cells considered per turn; pairs are drawn from these. */
	readonly width?: number;
	/** Turns played in each rollout before scoring the board. */
	readonly rolloutTurns?: number;
	readonly exploration?: number;
	readonly rng?: Rng;
}

export class MctsAgent implements Agent {
	readonly name = "mcts";
	private readonly iterations: number;
	private readonly width: number;
	private readonly rolloutTurns: number;
	private readonly exploration: number;
	private readonly rng: Rng;

	constructor(options: MctsOptions = {}) {
		this.iterations = options.iterations ?? 300;
		this.width = options.width ?? 8;
		this.rolloutTurns = options.rolloutTurns ?? 4;
		this.exploration = options.exploration ?? 0.7;
		this.rng = options.rng ?? mulberry32(1);
	}

	async chooseMove(state: GameState): Promise<Move> {
		return this.search(state);
	}

	/** Synchronous search, for tests and the tournament. */
	search(state: GameState): Move {
		const root = SearchBoard.from(state);
		const me = colourOf(state.toMove);
		const firstRequired = requiredStones(state);
		const rootMoves = generateMoves(root, me, firstRequired, this.width);
		const toMove = (cells: number[]): Move => ({
			positions: cells.map((c) => ({
				row: Math.floor(c / state.size),
				col: c % state.size,
			})),
		});
		const [only] = rootMoves;
		if (rootMoves.length === 1 && only) return toMove(only);

		const tree = newNode(null, other(me), null, false);
		tree.untried = rootMoves;
		for (let i = 0; i < this.iterations; i += 1) {
			const board = root.clone();
			let node = tree;
			// Select.
			while (!node.terminal && node.untried?.length === 0) {
				node = this.select(node);
				for (const c of node.move ?? []) board.place(c, node.mover);
			}
			// Expand.
			if (!node.terminal) {
				const mover = other(node.mover);
				if (node.untried === null) {
					node.untried = board.isFull()
						? []
						: generateMoves(board, mover, 2, this.width);
				}
				const move = node.untried.shift();
				if (move) {
					let won = false;
					for (const c of move) won = board.place(c, mover) || won;
					const child = newNode(move, mover, node, won);
					node.children.push(child);
					node = child;
				}
			}
			// Simulate, then back up from the mover's point of view.
			let value = node.terminal ? 1 : this.rollout(board, node.mover);
			for (let n: Node | null = node; n; n = n.parent) {
				n.visits += 1;
				n.value += value;
				value = 1 - value;
			}
		}
		const best = tree.children.reduce((a, b) => (b.visits > a.visits ? b : a));
		return toMove(best.move ?? []);
	}

	private select(node: Node): Node {
		const logN = Math.log(node.visits);
		let best = node.children[0] as Node;
		let bestScore = Number.NEGATIVE_INFINITY;
		for (const child of node.children) {
			const score =
				child.value / child.visits +
				this.exploration * Math.sqrt(logN / child.visits);
			if (score > bestScore) {
				bestScore = score;
				best = child;
			}
		}
		return best;
	}

	/** Plays a few noisy greedy turns; returns the value for `lastMover`. */
	private rollout(board: SearchBoard, lastMover: Colour): number {
		let mover = other(lastMover);
		for (let t = 0; t < this.rolloutTurns; t += 1) {
			if (board.isFull()) return 0.5;
			const moves = generateMoves(board, mover, 2, 4);
			const pick = Math.floor(this.rng() * Math.min(3, moves.length));
			const move = moves[pick] ?? moves[0] ?? [];
			let won = false;
			for (const c of move) won = board.place(c, mover) || won;
			if (won) return mover === lastMover ? 1 : 0;
			mover = other(mover);
		}
		return 1 / (1 + Math.exp(-board.evaluate(lastMover) / 150));
	}
}
