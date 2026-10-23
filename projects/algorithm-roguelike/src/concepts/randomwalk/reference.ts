// Depth-first search and the random walk. DFS follows one path as deep as it can, backtracking with a
// stack; a drunkard's walk wanders one random step at a time, carving floor, until enough is open.
import type { Rng } from "../../core/rng";

/** The order DFS visits a graph's nodes from `start`, with an explicit stack; neighbors in list order. */
export function dfsOrder(
	graph: Record<string, string[]>,
	start: string,
): { node: string; stack: string[] }[] {
	const seen = new Set<string>();
	const stack = [start];
	const out: { node: string; stack: string[] }[] = [];
	while (stack.length) {
		const node = stack.pop() as string;
		if (seen.has(node)) continue;
		seen.add(node);
		// Push in reverse so the first neighbor is explored first.
		for (const n of [...(graph[node] ?? [])].reverse())
			if (!seen.has(n)) stack.push(n);
		out.push({ node, stack: [...stack] });
	}
	return out;
}

/**
 * Carve a cave into a w × h grid of walls: start in the middle and step in a random direction (staying a
 * cell inside the edge), turning each cell visited to floor, until `coverage` of the grid is floor.
 */
export function drunkardsWalk(
	w: number,
	h: number,
	coverage: number,
	rng: Rng,
): { open: boolean[]; path: [number, number][] } {
	const open = Array<boolean>(w * h).fill(false);
	let x = w >> 1;
	let y = h >> 1;
	let carved = 0;
	const goal = Math.floor((w - 2) * (h - 2) * coverage);
	const path: [number, number][] = [];
	const dirs: [number, number][] = [
		[1, 0],
		[-1, 0],
		[0, 1],
		[0, -1],
	];
	while (carved < goal) {
		if (!open[y * w + x]) {
			open[y * w + x] = true;
			carved++;
		}
		path.push([x, y]);
		const [dx, dy] = rng.pick(dirs);
		x = Math.min(w - 2, Math.max(1, x + dx));
		y = Math.min(h - 2, Math.max(1, y + dy));
	}
	return { open, path };
}
