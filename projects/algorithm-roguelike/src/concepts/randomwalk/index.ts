import {
	emptyFloor,
	FLOOR,
	type Floor,
	index,
	type Point,
	rows,
	SHRINE,
	STAIRS,
} from "../../core/grid";
import { Rng } from "../../core/rng";
import type {
	Concept,
	Ctx,
	Frame,
	Generated,
	PuzzleStep,
} from "../../core/types";
import { bfs } from "../bfs/reference";
import { choice, draw } from "../util";
import { dfsOrder, drunkardsWalk } from "./reference";

const W = 46;
const H = 19;

/** A cave from a drunkard's walk, with the shrine in a carved clearing and the stairs as far away as possible. */
export function cave(ctx: Ctx): Generated {
	const f = emptyFloor(W, H);
	const { open } = drunkardsWalk(W, H, 0.4, ctx.rng);
	open.forEach((o, i) => {
		if (o) f.tiles[i] = FLOOR;
	});
	const start: Point = [W >> 1, H >> 1];
	const dist = bfs(rows(f), start);
	const cells = f.tiles.flatMap((t, i) => (t === FLOOR ? [i] : []));
	const far = (i: number) =>
		(dist[Math.floor(i / W)] as number[])[i % W] as number;
	const stairs = cells.reduce((a, b) => (far(b) > far(a) ? b : a));
	f.tiles[stairs] = STAIRS;
	const mid = cells.filter((i) => far(i) > 6 && far(i) < far(stairs) - 6);
	const s = ctx.rng.pick(
		mid.length ? mid : cells.filter((i) => i !== stairs && far(i) > 0),
	);
	const [sx, sy] = [s % W, Math.floor(s / W)];
	for (let y = sy - 1; y <= sy + 1; y++)
		for (let x = sx - 1; x <= sx + 1; x++)
			if (
				x > 0 &&
				y > 0 &&
				x < W - 1 &&
				y < H - 1 &&
				f.tiles[index(f, x, y)] !== STAIRS
			)
				f.tiles[index(f, x, y)] = FLOOR;
	f.tiles[s] = SHRINE;
	return { floor: f, start };
}

const GRAPH: Record<string, string[]> = {
	A: ["B", "C"],
	B: ["A", "D", "E"],
	C: ["A", "F"],
	D: ["B"],
	E: ["B", "F", "G"],
	F: ["C", "E"],
	G: ["E"],
};
const PICTURE = [
	"  A ------- C",
	"  |          \\",
	"  B --- E --- F",
	"  |     |",
	"  D     G",
];
// The edges drawn above, kept in step with GRAPH.
const EDGES = ["A-B", "A-C", "B-D", "B-E", "C-F", "E-F", "E-G"];

function shuffledGraph(rng: Rng): Record<string, string[]> {
	const g: Record<string, string[]> = {};
	for (const [k, v] of Object.entries(GRAPH)) g[k] = rng.shuffle([...v]);
	return g;
}

const walkFrames = (f: Floor, path: Point[], every: number): Frame[] => {
	const marks = new Map<number, string>();
	const out: Frame[] = [];
	for (const [k, [x, y]] of path.entries()) {
		marks.set(index(f, x, y), ".");
		if (k % every === 0 || k === path.length - 1) {
			const m = new Map(marks);
			m.set(index(f, x, y), "@");
			out.push({
				caption: `Step ${k + 1}: a random step; every cell walked on becomes floor.`,
				lines: draw({ ...f, tiles: f.tiles.map(() => "#") }, m),
				data: [`floor cells: ${marks.size}`],
			});
		}
	}
	return out;
};

function frames(seed: number): Frame[] {
	const g = shuffledGraph(new Rng(seed));
	const out: Frame[] = dfsOrder(g, "A").map((t, i, all) => ({
		caption: `DFS visits ${t.node}${i ? ", going as deep as it can before backing up" : ""}.`,
		lines: PICTURE,
		data: [
			`visited: ${all
				.slice(0, i + 1)
				.map((x) => x.node)
				.join(" ")}`,
			`stack (top at the right): ${t.stack.join(" ") || "(empty)"}`,
			`neighbors: ${Object.entries(g)
				.map(([k, v]) => `${k}→${v.join("")}`)
				.join(" ")}`,
		],
	}));
	const f = emptyFloor(24, 10);
	const rng = new Rng(seed);
	const { path } = drunkardsWalk(24, 10, 0.35, rng);
	return [
		...out,
		...walkFrames(f, path, Math.max(1, Math.floor(path.length / 12))),
	];
}

export const concept: Concept = {
	id: "randomwalk",
	name: "DFS and random walk",
	tier: 2,
	requires: ["stack", "prng"],
	unlocks: "cave floors, carved by a drunkard's walk.",
	complexity: {
		time: "DFS O(V + E); a walk takes steps until enough is carved",
		space: "O(V)",
	},
	reading: {
		title: "Random Walk Cave Generation (RogueBasin)",
		url: "https://www.roguebasin.com/index.php/Random_Walk_Cave_Generation",
	},
	lesson: {
		text: [
			"Depth-first search (DFS) explores by always going deeper: from a node, go to an unvisited neighbor, and from there to another, until you are stuck. Then back up to the last place with an unexplored way out.",
			"Backing up is a stack. Push the neighbors you have not taken; pop the next one to explore. Swap the stack for a queue and you get BFS.",
			"A random walk drops the bookkeeping: from where you are, take one random step, again and again. A drunkard's walk carves a cave this way, turning every wall it steps on into floor until enough of the map is open.",
			"Every cell carved was reached by a walk from the start, so the whole cave is connected without any extra work.",
		],
		frames,
	},
	puzzle(seed) {
		const rng = new Rng(seed);
		const steps: PuzzleStep[] = [];
		const g = shuffledGraph(rng);
		const order = dfsOrder(g, "A");
		for (let k = 0; k < order.length - 1 && steps.length < 5; k++) {
			const t = order[k] as (typeof order)[0];
			const next = (order[k + 1] as (typeof order)[0]).node;
			const visited = order.slice(0, k + 1).map((x) => x.node);
			steps.push(
				choice(
					rng,
					`Edges: ${EDGES.join(", ")}. Neighbors are tried in this order: ${Object.entries(
						g,
					)
						.map(([n, v]) => `${n}: ${v.join(", ")}`)
						.join(
							"; ",
						)}. Visited so far: ${visited.join(" ")}. Which node does DFS visit next?`,
					next,
					Object.keys(g).filter((n) => !visited.includes(n)),
					`DFS keeps going from the newest node: the stack is ${t.stack.join(" ")} (top at the right), and the top unvisited node is ${next}.`,
					PICTURE,
				),
			);
		}
		steps.push(
			choice(
				rng,
				"A drunkard's walk carves a cave. Why is every floor cell reachable from the start?",
				"Every carved cell was walked onto from the start",
				[
					"The walk checks connections with BFS afterwards",
					"Walls are added only at the edges",
					"It isn't: caves need fixing afterwards",
				],
				"The walker carves only where it stands, and it got there by walking from the start.",
			),
		);
		return {
			intro: "Follow depth-first search through a small graph.",
			steps,
			slack: 1,
		};
	},
	hooks: { generator: { priority: 2, generate: (ctx) => cave(ctx) } },
	sandbox(floor, from, seed) {
		const rng = new Rng(seed);
		const f = { ...floor, tiles: [...floor.tiles] };
		let [x, y] = from;
		const path: Point[] = [];
		for (let i = 0; i < 300; i++) {
			path.push([x, y]);
			const [dx, dy] = rng.pick([
				[1, 0],
				[-1, 0],
				[0, 1],
				[0, -1],
			] as Point[]);
			if (f.tiles[index(f, x + dx, y + dy)] !== "#") [x, y] = [x + dx, y + dy];
		}
		const marks = new Map<number, string>();
		return path.flatMap(([px, py], k) => {
			marks.set(index(f, px, py), "*");
			if (k % 10) return [];
			const m = new Map(marks);
			m.set(index(f, px, py), "@");
			return [
				{
					caption: `Step ${k + 1} of a random walk on this floor (it can't walk through walls).`,
					lines: draw(f, m),
					data: [`cells walked on: ${marks.size}`],
				},
			];
		});
	},
};
