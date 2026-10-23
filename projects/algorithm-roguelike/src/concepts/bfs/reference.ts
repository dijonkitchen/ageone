// Breadth-first search on a grid with a queue: distances in steps from a start cell, exploring every cell
// one step away before any cell two steps away. Self-contained, so it also runs in the code-mode sandbox.

/**
 * Steps from `start` to every cell of `grid` (rows of text, '#' is a wall), moving up, down, left, or
 * right; -1 where a cell can't be reached. Neighbors are queued in the order right, left, down, up.
 */
export function bfs(grid: string[], start: [number, number]): number[][] {
	const h = grid.length;
	const w = h ? (grid[0] as string).length : 0;
	const dist = grid.map((row) => Array.from(row, () => -1));
	const [sx, sy] = start;
	if (sy < 0 || sy >= h || sx < 0 || sx >= w || grid[sy]?.[sx] === "#")
		return dist;
	(dist[sy] as number[])[sx] = 0;
	const queue: [number, number][] = [[sx, sy]];
	for (let head = 0; head < queue.length; head++) {
		const [x, y] = queue[head] as [number, number];
		const d = (dist[y] as number[])[x] as number;
		for (const [dx, dy] of [
			[1, 0],
			[-1, 0],
			[0, 1],
			[0, -1],
		] as [number, number][]) {
			const nx = x + dx;
			const ny = y + dy;
			if (
				nx < 0 ||
				ny < 0 ||
				nx >= w ||
				ny >= h ||
				grid[ny]?.[nx] === "#" ||
				(dist[ny] as number[])[nx] !== -1
			)
				continue;
			(dist[ny] as number[])[nx] = d + 1;
			queue.push([nx, ny]);
		}
	}
	return dist;
}

/** The order BFS takes cells off the queue, with the queue after each, for lessons and puzzles. */
export function bfsTrace(
	grid: string[],
	start: [number, number],
): { cell: [number, number]; queue: [number, number][]; dist: number }[] {
	const dist = grid.map((row) => Array.from(row, () => -1));
	const out: {
		cell: [number, number];
		queue: [number, number][];
		dist: number;
	}[] = [];
	const [sx, sy] = start;
	(dist[sy] as number[])[sx] = 0;
	const queue: [number, number][] = [[sx, sy]];
	while (queue.length) {
		const [x, y] = queue.shift() as [number, number];
		for (const [dx, dy] of [
			[1, 0],
			[-1, 0],
			[0, 1],
			[0, -1],
		] as [number, number][]) {
			const nx = x + dx;
			const ny = y + dy;
			if (
				ny < 0 ||
				ny >= grid.length ||
				nx < 0 ||
				nx >= (grid[ny] as string).length ||
				grid[ny]?.[nx] === "#" ||
				(dist[ny] as number[])[nx] !== -1
			)
				continue;
			(dist[ny] as number[])[nx] = ((dist[y] as number[])[x] as number) + 1;
			queue.push([nx, ny]);
		}
		out.push({
			cell: [x, y],
			queue: [...queue],
			dist: (dist[y] as number[])[x] as number,
		});
	}
	return out;
}
