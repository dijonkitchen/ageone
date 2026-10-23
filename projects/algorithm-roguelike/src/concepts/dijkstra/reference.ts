// Dijkstra's algorithm: shortest distances when steps cost different amounts. Settle the unsettled cell
// with the smallest tentative distance (a priority queue finds it), then relax its neighbors. Roguelikes
// run it over the whole floor from the player to get a "Dijkstra map" monsters roll downhill on.
import { popInPlace, pushInPlace } from "../heap/reference";

const STEPS: [number, number][] = [
	[1, 0],
	[-1, 0],
	[0, 1],
	[0, -1],
	[1, 1],
	[1, -1],
	[-1, 1],
	[-1, -1],
];

/**
 * Distances over a grid (rows of text, '#' blocks) from sources [x, y, starting value], moving in 8
 * directions; entering a cell costs cost(x, y). Unreached cells are Infinity. `onSettle` sees each cell
 * as its distance becomes final.
 */
export function dijkstraMap(
	grid: string[],
	sources: [number, number, number][],
	cost: (x: number, y: number) => number = () => 1,
	onSettle?: (i: number, d: number) => void,
): number[] {
	const h = grid.length;
	const w = h ? (grid[0] as string).length : 0;
	const dist = Array<number>(w * h).fill(Number.POSITIVE_INFINITY);
	const heap: number[][] = [];
	for (const [x, y, d] of sources) {
		if (
			grid[y]?.[x] === undefined ||
			grid[y]?.[x] === "#" ||
			d >= (dist[y * w + x] as number)
		)
			continue;
		dist[y * w + x] = d;
		pushInPlace(heap, [d, y * w + x]);
	}
	while (heap.length) {
		const [d, i] = popInPlace(heap) as [number, number];
		if (d > (dist[i] as number)) continue; // a stale entry: this cell was settled with less
		onSettle?.(i, d);
		const x = i % w;
		const y = Math.floor(i / w);
		for (const [dx, dy] of STEPS) {
			const nx = x + dx;
			const ny = y + dy;
			if (nx < 0 || ny < 0 || nx >= w || ny >= h || grid[ny]?.[nx] === "#")
				continue;
			const nd = d + cost(nx, ny);
			if (nd < (dist[ny * w + nx] as number)) {
				dist[ny * w + nx] = nd;
				pushInPlace(heap, [nd, ny * w + nx]);
			}
		}
	}
	return dist;
}

/** A map for fleeing: the chase map times -1.2, rolled out again, so cornered monsters slip past you. */
export function fleeMap(
	grid: string[],
	chase: number[],
	cost?: (x: number, y: number) => number,
): number[] {
	const w = grid.length ? (grid[0] as string).length : 0;
	const sources: [number, number, number][] = [];
	chase.forEach((d, i) => {
		if (Number.isFinite(d)) sources.push([i % w, Math.floor(i / w), -1.2 * d]);
	});
	return dijkstraMap(grid, sources, cost);
}

export type Graph = Record<string, [string, number][]>;

/** Dijkstra on a small graph, for lessons: the order nodes settle, with the tentative distances before each. */
export function dijkstraGraph(
	graph: Graph,
	start: string,
): { node: string; dist: number; tentative: Record<string, number> }[] {
	const dist: Record<string, number> = Object.fromEntries(
		Object.keys(graph).map((n) => [n, Number.POSITIVE_INFINITY]),
	);
	dist[start] = 0;
	const done = new Set<string>();
	const out: {
		node: string;
		dist: number;
		tentative: Record<string, number>;
	}[] = [];
	for (;;) {
		const open = Object.keys(graph)
			.filter((n) => !done.has(n) && Number.isFinite(dist[n]))
			.sort(
				(a, b) =>
					(dist[a] as number) - (dist[b] as number) || a.localeCompare(b),
			);
		const node = open[0];
		if (!node) return out;
		out.push({ node, dist: dist[node] as number, tentative: { ...dist } });
		done.add(node);
		for (const [n, wgt] of graph[node] ?? [])
			if (!done.has(n) && (dist[node] as number) + wgt < (dist[n] as number))
				dist[n] = (dist[node] as number) + wgt;
	}
}
