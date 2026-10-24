// Recursive shadowcasting (after Björn Bergström's write-up on RogueBasin): field of view on a grid.
// Each of the 8 octants is scanned row by row outward from the viewer; a wall casts a shadow, and the
// scan recurses on the lit slopes past it, so each cell is looked at about once.

const MULT = [
	[1, 0, 0, -1, -1, 0, 0, 1],
	[0, 1, -1, 0, 0, -1, 1, 0],
	[0, 1, 1, 0, 0, -1, -1, 0],
	[1, 0, 0, 1, -1, 0, 0, -1],
];

/** Cells (as y * width + x) visible from (ox, oy) within `radius`, octant by octant; walls are '#'. */
export function fovByOctant(
	grid: string[],
	ox: number,
	oy: number,
	radius: number,
): number[][] {
	const h = grid.length;
	const w = h ? (grid[0] as string).length : 0;
	const blocks = (x: number, y: number) =>
		x < 0 || y < 0 || x >= w || y >= h || grid[y]?.[x] === "#";
	const octants: number[][] = [];
	const r2 = radius * radius;
	for (let oct = 0; oct < 8; oct++) {
		const seen: number[] = [];
		const xx = MULT[0]?.[oct] as number;
		const xy = MULT[1]?.[oct] as number;
		const yx = MULT[2]?.[oct] as number;
		const yy = MULT[3]?.[oct] as number;
		const cast = (row: number, startIn: number, end: number) => {
			let start = startIn;
			if (start < end) return;
			let newStart = 0;
			for (let j = row; j <= radius; j++) {
				let dx = -j - 1;
				const dy = -j;
				let blocked = false;
				while (dx <= 0) {
					dx++;
					const X = ox + dx * xx + dy * xy;
					const Y = oy + dx * yx + dy * yy;
					const lSlope = (dx - 0.5) / (dy + 0.5);
					const rSlope = (dx + 0.5) / (dy - 0.5);
					if (start < rSlope) continue;
					if (end > lSlope) break;
					if (dx * dx + dy * dy <= r2 && X >= 0 && Y >= 0 && X < w && Y < h)
						seen.push(Y * w + X);
					if (blocked) {
						if (blocks(X, Y)) {
							newStart = rSlope;
							continue;
						}
						blocked = false;
						start = newStart;
					} else if (blocks(X, Y) && j < radius) {
						blocked = true;
						cast(j + 1, start, lSlope);
						newStart = rSlope;
					}
				}
				if (blocked) break;
			}
		};
		cast(1, 1, 0);
		octants.push(seen);
	}
	return octants;
}

/** Every cell visible from (ox, oy), the viewer's own cell included, sorted. */
export function fov(
	grid: string[],
	ox: number,
	oy: number,
	radius: number,
): number[] {
	const w = grid.length ? (grid[0] as string).length : 0;
	return [
		...new Set([oy * w + ox, ...fovByOctant(grid, ox, oy, radius).flat()]),
	].sort((a, b) => a - b);
}
