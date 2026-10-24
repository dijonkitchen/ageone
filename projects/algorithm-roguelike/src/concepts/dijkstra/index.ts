import { MONSTERS, open } from "../../core/engine";
import { DIRS8, index, type Point, rows } from "../../core/grid";
import { Rng } from "../../core/rng";
import type {
	Concept,
	Ctx,
	Frame,
	Monster,
	PuzzleStep,
	State,
} from "../../core/types";
import { choice, digit, draw, mapOf } from "../util";
import { dijkstraGraph, dijkstraMap, fleeMap, type Graph } from "./reference";

const TRACK = 16; // how far (in cost) a monster tracks you
const CROWD = 4; // extra cost of a cell another monster stands in, so packs spread out and surround

function brain(ctx: Ctx, s: State, m: Monster): Point | null {
	const { x, y } = s.player;
	const kind = MONSTERS[m.kind];
	const grid = rows(s.floor);
	const crowd = new Set(
		s.monsters.filter((o) => o !== m).map((o) => index(s.floor, o.x, o.y)),
	);
	const cost = (cx: number, cy: number) =>
		1 + (crowd.has(index(s.floor, cx, cy)) ? CROWD : 0);
	const fleeing = !!kind && m.hp * 3 <= kind.hp && kind.hp > 2;
	if (!fleeing && Math.max(Math.abs(m.x - x), Math.abs(m.y - y)) <= 1)
		return [x, y];
	const options = DIRS8.map(([dx, dy]) => [m.x + dx, m.y + dy] as Point).filter(
		([nx, ny]) => open(s, nx, ny),
	);
	if (kind?.erratic && ctx.rng.chance(0.5))
		return options.length ? ctx.rng.pick(options) : null;
	const chase = dijkstraMap(grid, [[x, y, 0]], cost);
	const here = chase[index(s.floor, m.x, m.y)] ?? Number.POSITIVE_INFINITY;
	if (here > TRACK)
		return options.length && ctx.rng.chance(0.5) ? ctx.rng.pick(options) : null;
	const map = fleeing ? fleeMap(grid, chase, cost) : chase;
	let best: Point | null = null;
	let bestValue = map[index(s.floor, m.x, m.y)] ?? Number.POSITIVE_INFINITY;
	for (const p of options) {
		const v = map[index(s.floor, p[0], p[1])] ?? Number.POSITIVE_INFINITY;
		if (v < bestValue) [best, bestValue] = [p, v];
	}
	return best;
}

const GRAPH_EDGES: [string, string][] = [
	["A", "B"],
	["A", "C"],
	["B", "C"],
	["B", "D"],
	["C", "E"],
	["D", "E"],
	["D", "F"],
	["E", "F"],
];

function randomGraph(rng: Rng): { graph: Graph; edges: string[] } {
	const graph: Graph = { A: [], B: [], C: [], D: [], E: [], F: [] };
	const edges: string[] = [];
	for (const [a, b] of GRAPH_EDGES) {
		const w = rng.range(1, 9);
		graph[a]?.push([b, w]);
		graph[b]?.push([a, w]);
		edges.push(`${a}–${b} ${w}`);
	}
	return { graph, edges };
}

const fmt = (d: number | undefined) =>
	d === undefined || !Number.isFinite(d) ? "∞" : String(d);

const DEMO = [
	"##############",
	"#......~~~...#",
	"#.##...~~~.#.#",
	"#..#...~~~.#.#",
	"#.......~~...#",
	"##############",
];

function mapFrames(
	grid: string[],
	from: Point,
	cost: (x: number, y: number) => number,
	every: number,
): Frame[] {
	const f = mapOf(grid);
	const marks = new Map<number, string>();
	const out: Frame[] = [];
	let n = 0;
	dijkstraMap(grid, [[from[0], from[1], 0]], cost, (i, d) => {
		marks.set(i, digit(d));
		if (n++ % every === 0)
			out.push({
				caption: `Settle the closest unsettled cell (distance ${d}); its neighbors get tentative distances.`,
				lines: draw(f, new Map(marks)),
				data: [`settled: ${marks.size}`],
			});
	});
	out.push({
		caption:
			"The finished Dijkstra map: monsters step downhill on it to reach you.",
		lines: draw(f, marks),
		data: [`settled: ${marks.size}`],
	});
	return out;
}

export const concept: Concept = {
	id: "dijkstra",
	name: "Dijkstra",
	tier: 2,
	requires: ["bfs", "heap"],
	unlocks:
		"Dijkstra maps: monsters chase you around walls, spread out to surround you, and flee when hurt.",
	complexity: { time: "O((V + E) log V) with a binary heap", space: "O(V)" },
	reading: {
		title: "The Incredible Power of Dijkstra Maps (RogueBasin)",
		url: "https://www.roguebasin.com/index.php/The_Incredible_Power_of_Dijkstra_Maps",
	},
	lesson: {
		text: [
			"BFS finds shortest paths when every step costs the same. Dijkstra's algorithm handles steps that cost different amounts, like wading through water (~) or squeezing past another monster.",
			"Every node gets a tentative distance: 0 at the start and infinity elsewhere. Repeatedly settle the unsettled node with the smallest tentative distance; its distance is now final. Then relax its neighbors: if going through it is shorter, lower theirs.",
			"Finding the smallest tentative distance quickly is exactly what a priority queue is for, which is why the heap comes first.",
			"Run from the player over the whole floor, it gives a Dijkstra map: each cell holds its distance to you. A monster steps to its lowest neighbor and rolls downhill to you, around any walls.",
			"Multiply the map by -1.2 and roll it out again, and hurt monsters run away without cornering themselves.",
		],
		frames: () =>
			mapFrames(DEMO, [1, 1], (x, y) => (DEMO[y]?.[x] === "~" ? 3 : 1), 4),
	},
	puzzle(seed) {
		const rng = new Rng(seed);
		const { graph, edges } = randomGraph(rng);
		const order = dijkstraGraph(graph, "A");
		const steps: PuzzleStep[] = [];
		for (const [k, t] of order.entries()) {
			if (k === 0 || k === order.length - 1) continue;
			const settled = order.slice(0, k).map((o) => o.node);
			const table = Object.keys(graph).map(
				(n) =>
					`${n} ${settled.includes(n) ? `${fmt(t.tentative[n])} ✓` : fmt(t.tentative[n])}`,
			);
			if (k % 2 === 1)
				steps.push(
					choice(
						rng,
						`Edges: ${edges.join(", ")}. Settled (✓) and tentative distances: ${table.join(", ")}. Which node is settled next?`,
						t.node,
						Object.keys(graph).filter((n) => !settled.includes(n)),
						`${t.node} has the smallest tentative distance (${t.dist}) among the unsettled nodes${Object.values(t.tentative).filter((d) => d === t.dist).length > 1 ? "; ties go in name order" : ""}.`,
					),
				);
			else
				steps.push(
					choice(
						rng,
						`Edges: ${edges.join(", ")}. What is the shortest distance from A to ${t.node}?`,
						String(t.dist),
						[
							String(t.dist + 1),
							String(t.dist - 1),
							String(t.dist + 2),
							String(t.dist + 3),
						],
						`Settled distances are final: ${t.node} settles at ${t.dist}.`,
					),
				);
		}
		return {
			intro: "Run Dijkstra's algorithm on a small weighted graph.",
			steps: steps.slice(0, 6),
			slack: 2,
		};
	},
	hooks: { brain: { priority: 1, step: brain } },
	sandbox: (floor, from) => mapFrames(rows(floor), from, () => 1, 40),
};
