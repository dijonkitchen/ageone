// A 2D grid stored row by row in one flat array: (x, y) lives at y * width + x.

export const toIndex = (width: number, x: number, y: number) => y * width + x;

export const toPoint = (width: number, i: number): [number, number] => [
	i % width,
	Math.floor(i / width),
];

/** The indices of a cell's four neighbors that are inside the grid. */
export function neighbors(width: number, height: number, i: number): number[] {
	const [x, y] = toPoint(width, i);
	const out: number[] = [];
	if (x + 1 < width) out.push(i + 1);
	if (x > 0) out.push(i - 1);
	if (y + 1 < height) out.push(i + width);
	if (y > 0) out.push(i - width);
	return out;
}
