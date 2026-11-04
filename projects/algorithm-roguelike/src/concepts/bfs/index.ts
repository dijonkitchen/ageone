import { DIRS8, inBounds, index, type Point, rows } from "../../core/grid";
import { Rng } from "../../core/rng";
import type {
	CodeTrial,
	Concept,
	Frame,
	PuzzleStep,
	TestCase,
} from "../../core/types";
import { choice, digit, draw, mapOf, xy } from "../util";
import { bfs, bfsTrace } from "./reference";

const DEMO = [
	"#########",
	"#.......#",
	"#.##.#..#",
	"#....#..#",
	"#.#...#.#",
	"#########",
];
const CAVE_RADIUS = 8;

const validDistances = (r: unknown) =>
	Array.isArray(r) && r.every((row) => Array.isArray(row));

function traceFrames(grid: string[], start: Point, limit = 40): Frame[] {
	const f = mapOf(grid);
	const done = new Map<number, string>();
	const out: Frame[] = [];
	const trace = bfsTrace(grid, start);
	for (const [k, t] of trace.entries()) {
		if (k >= limit) break;
		done.set(index(f, t.cell[0], t.cell[1]), digit(t.dist));
		const marks = new Map(done);
		for (const q of t.queue) marks.set(index(f, q[0], q[1]), "o");
		marks.set(index(f, t.cell[0], t.cell[1]), "@");
		out.push({
			caption: `Take ${xy(t.cell)} off the front of the queue (distance ${t.dist}) and queue its unvisited neighbors.`,
			lines: draw(f, marks),
			data: [
				`queue: ${t.queue.map(xy).join(" ") || "(empty)"}`,
				`visited: ${done.size}`,
			],
		});
	}
	return out;
}

function randomMap(rng: Rng, w: number, h: number, walls: number): string[] {
	return Array.from({ length: h }, () =>
		Array.from({ length: w }, () => (rng.chance(walls) ? "#" : ".")).join(""),
	);
}

const same = (a: unknown, b: unknown) =>
	JSON.stringify(a) === JSON.stringify(b);

function suite(): TestCase[] {
	const cases: [string, string[], Point][] = [
		["an open 3 by 3 room from a corner", ["...", "...", "..."], [0, 0]],
		["a wall in the way", [".#.", ".#.", "..."], [0, 0]],
		["a cell that can't be reached is -1", ["..#.", "..#.", "###."], [0, 0]],
		["starting in the middle", [".....", ".....", "....."], [2, 1]],
		["a start on a wall reaches nothing", ["#.", ".."], [0, 0]],
		["one cell", ["."], [0, 0]],
		["the demo map", DEMO, [1, 1]],
	];
	const rng = new Rng(1234);
	for (let k = 0; k < 4; k++)
		cases.push([
			`random floor ${k + 1}`,
			randomMap(rng, 46, 19, 0.3),
			[rng.int(46), rng.int(19)],
		]);
	return cases.map(([name, grid, start]) => ({
		name,
		run(call) {
			const got = call("bfs", grid, start);
			const want = bfs(grid, start);
			if (same(got, want)) return null;
			if (!Array.isArray(got))
				return `expected rows of distances, got ${JSON.stringify(got)?.slice(0, 80)}`;
			for (let y = 0; y < want.length; y++)
				for (let x = 0; x < (want[y] as number[]).length; x++) {
					const g = (got as number[][])[y]?.[x];
					const wv = (want[y] as number[])[x];
					if (g !== wv)
						return `distance at (${x},${y}) should be ${wv}, got ${g}`;
				}
			return "the result has the wrong shape";
		},
	}));
}

const trial: CodeTrial = {
	exports: ["bfs"],
	docs: [
		"Write bfs(grid, start).",
		"grid is an array of strings, one per row; '#' is a wall and anything else is open.",
		"start is [x, y]. Moves go right, left, down, or up (no diagonals).",
		"Return rows of numbers, the same size as grid: the fewest moves from start to each cell, 0 at start, and -1 for walls and cells you can't reach.",
		"In the game your bfs reveals the room you stand in, and nearby cave in caves.",
	].join("\n"),
	starter: [
		"function bfs(grid, start) {",
		"  const h = grid.length, w = grid[0].length;",
		"  const dist = grid.map(row => Array.from(row, () => -1));",
		"  const [sx, sy] = start;",
		"  if (grid[sy][sx] === '#') return dist;",
		"  dist[sy][sx] = 0;",
		"  const queue = [[sx, sy]];",
		"  // Take cells off the front of the queue; give each open, unvisited neighbor",
		"  // a distance one more than this cell's, and put it on the back of the queue.",
		"  return dist;",
		"}",
	].join("\n"),
	suite: suite(),
	budgetMs: 1500,
	reference: { bfs },
};

export const concept: Concept = {
	id: "bfs",
	name: "Queue and breadth-first search",
	tier: 1,
	requires: ["grid"],
	unlocks:
		"flood-fill reveal: you see the whole room you stand in (and nearby cave).",
	complexity: { time: "O(V + E): each cell is queued once", space: "O(V)" },
	reading: {
		title: "Breadth First Search (Red Blob Games)",
		url: "https://www.redblobgames.com/pathfinding/tower-defense/",
	},
	lesson: {
		text: [
			"A queue is a line: you join at the back and leave from the front, so the first in is the first out.",
			"Breadth-first search (BFS) explores a map in rings. Put the start in the queue. Then, again and again, take the cell at the front, and add each open neighbor you have not seen yet to the back, one step further than the cell you took.",
			"Because the queue keeps cells in order of distance, every cell is reached first by a shortest path, and its distance is final the moment it is queued.",
			"A flood fill is the same search: every cell reached is in the same connected area. The game uses it to light up the whole room you are standing in.",
			"Each cell is queued at most once and each of its edges is looked at once, so BFS is linear in the size of the map.",
		],
		frames: () => traceFrames(DEMO, [1, 1]),
	},
	puzzle(seed) {
		const rng = new Rng(seed);
		const start: Point = [1 + rng.int(3), 1];
		const trace = bfsTrace(DEMO, start);
		const f = mapOf(DEMO);
		const steps: PuzzleStep[] = [];
		const done = new Map<number, string>();
		for (let k = 0; k < trace.length - 1 && steps.length < 7; k++) {
			const t = trace[k] as (typeof trace)[0];
			done.set(index(f, t.cell[0], t.cell[1]), digit(t.dist));
			const next = trace[k + 1] as (typeof trace)[0];
			if (k % 2 === 1 || t.queue.length < 2) continue;
			const marks = new Map(done);
			for (const [i, q] of t.queue.entries())
				marks.set(index(f, q[0], q[1]), String.fromCharCode(65 + i));
			const label = (p: Point) => {
				const i = t.queue.findIndex((q) => q[0] === p[0] && q[1] === p[1]);
				return i >= 0 ? `${String.fromCharCode(65 + i)} ${xy(p)}` : xy(p);
			};
			steps.push(
				choice(
					rng,
					`The queue holds the lettered cells, in the order they were added (A first). Which cell does BFS visit next?`,
					label(next.cell),
					t.queue.slice(1).map(label),
					`A queue is first in, first out: the front of the queue, ${label(next.cell)}, was added before the others.`,
					draw(f, marks),
				),
			);
		}
		const dist = bfs(DEMO, start);
		const free = DEMO.flatMap((r, y) =>
			Array.from(r).flatMap((c, x) => (c === "#" ? [] : [[x, y] as Point])),
		);
		const target = rng.pick(
			free.filter(([x, y]) => ((dist[y] as number[])[x] as number) > 3),
		);
		const d = (dist[target[1]] as number[])[target[0]] as number;
		const marks = new Map([
			[index(f, start[0], start[1]), "S"],
			[index(f, target[0], target[1]), "T"],
		]);
		steps.push(
			choice(
				rng,
				"How many steps (no diagonals) does BFS say it takes from S to T?",
				String(d),
				[
					String(d - 1),
					String(d + 1),
					String(d + 2),
					String(
						Math.abs(target[0] - start[0]) + Math.abs(target[1] - start[1]),
					),
				],
				`BFS reaches T in ring ${d}: that is the shortest path around the walls.`,
				draw(f, marks),
			),
		);
		return {
			intro: "Play BFS by hand: the queue decides which cell comes next.",
			steps,
			slack: 2,
		};
	},
	hooks: {
		vision(ctx, s) {
			const f = s.floor;
			const here = f.room[index(f, s.player.x, s.player.y)] ?? -1;
			const grid =
				here >= 0
					? rows({
							...f,
							tiles: f.tiles.map((t, i) => (f.room[i] === here ? t : "#")),
						})
					: rows(f);
			const dist = ctx.code(
				"bfs",
				bfs,
				validDistances,
			)(grid, [s.player.x, s.player.y]);
			const out: number[] = [];
			for (let y = 0; y < f.h; y++)
				for (let x = 0; x < f.w; x++) {
					const d = dist[y]?.[x] ?? -1;
					if (d < 0 || (here < 0 && d > CAVE_RADIUS)) continue;
					out.push(index(f, x, y));
					if (here >= 0)
						for (const [dx, dy] of DIRS8)
							if (inBounds(f, x + dx, y + dy))
								out.push(index(f, x + dx, y + dy));
				}
			return out;
		},
	},
	code: trial,
	sandbox: (floor, from) => traceFrames(rows(floor), from, 400),
};
