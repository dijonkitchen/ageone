// Bresenham's line algorithm: the grid cells on a straight line from (x0, y0) to (x1, y1), using only
// integer adds and compares. Self-contained, so it also runs in the code-mode sandbox.

/** Every cell from (x0, y0) to (x1, y1) inclusive, each one step (possibly diagonal) from the last. */
export function line(
	x0: number,
	y0: number,
	x1: number,
	y1: number,
): [number, number][] {
	const dx = Math.abs(x1 - x0);
	const dy = -Math.abs(y1 - y0);
	const sx = x0 < x1 ? 1 : -1;
	const sy = y0 < y1 ? 1 : -1;
	let err = dx + dy;
	let x = x0;
	let y = y0;
	const out: [number, number][] = [];
	for (;;) {
		out.push([x, y]);
		if (x === x1 && y === y1) return out;
		const e2 = 2 * err;
		if (e2 >= dy) {
			err += dy;
			x += sx;
		}
		if (e2 <= dx) {
			err += dx;
			y += sy;
		}
	}
}

/** Whether `cells` is a valid digital line from a to b: Bresenham's or any other with the same guarantees. */
export function lineProblem(
	cells: unknown,
	x0: number,
	y0: number,
	x1: number,
	y1: number,
): string | null {
	if (
		!Array.isArray(cells) ||
		!cells.every(
			(c) => Array.isArray(c) && c.length === 2 && c.every(Number.isInteger),
		)
	)
		return "expected a list of [x, y] pairs of whole numbers";
	const pts = cells as [number, number][];
	const n = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)) + 1;
	if (pts.length !== n) return `expected ${n} cells, got ${pts.length}`;
	const [fx, fy] = pts[0] as [number, number];
	const [lx, ly] = pts.at(-1) as [number, number];
	if (fx !== x0 || fy !== y0)
		return `the line should start at (${x0},${y0}), not (${fx},${fy})`;
	if (lx !== x1 || ly !== y1)
		return `the line should end at (${x1},${y1}), not (${lx},${ly})`;
	const xMajor = Math.abs(x1 - x0) >= Math.abs(y1 - y0);
	for (let i = 0; i < pts.length; i++) {
		const [x, y] = pts[i] as [number, number];
		if (i > 0) {
			const [px, py] = pts[i - 1] as [number, number];
			if (Math.max(Math.abs(x - px), Math.abs(y - py)) !== 1)
				return `(${px},${py}) to (${x},${y}) is not one step`;
		}
		// Each cell must be within half a cell of the true line, measured across the line's long axis.
		const off = xMajor
			? x1 === x0
				? 0
				: Math.abs(y - (y0 + ((y1 - y0) * (x - x0)) / (x1 - x0)))
			: Math.abs(x - (x0 + ((x1 - x0) * (y - y0)) / (y1 - y0)));
		if (off > 0.5 + 1e-9)
			return `(${x},${y}) is ${off.toFixed(2)} cells off the true line`;
	}
	return null;
}
