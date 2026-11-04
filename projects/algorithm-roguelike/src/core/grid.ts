// Floors are 2D grids stored row by row in one flat array: the cell at (x, y) is at index y * w + x.
// The arrays and 2D grids concept teaches this layout.

export type Point = [number, number];

export const WALL = "#";
export const FLOOR = ".";
export const STAIRS = ">";
export const SHRINE = "_";

export interface Floor {
	w: number;
	h: number;
	tiles: string[]; // one character per cell
	room: number[]; // the room each cell belongs to, or -1 (corridors, caves)
	shrineRoom: number; // the safe room's id, or -1 when the safe area is around the shrine tile
	seen: number[]; // 1 once the player has seen the cell
}

export const index = (f: { w: number }, x: number, y: number) => y * f.w + x;
export const inBounds = (f: { w: number; h: number }, x: number, y: number) =>
	x >= 0 && y >= 0 && x < f.w && y < f.h;
export const tileAt = (f: Floor, x: number, y: number) =>
	inBounds(f, x, y) ? (f.tiles[index(f, x, y)] as string) : WALL;
export const passable = (t: string) => t !== WALL;

export function emptyFloor(w: number, h: number): Floor {
	return {
		w,
		h,
		tiles: Array(w * h).fill(WALL),
		room: Array(w * h).fill(-1),
		shrineRoom: -1,
		seen: Array(w * h).fill(0),
	};
}

/** The floor as rows of text, the form code-mode functions get. */
export const rows = (f: Floor): string[] =>
	Array.from({ length: f.h }, (_, y) =>
		f.tiles.slice(y * f.w, (y + 1) * f.w).join(""),
	);

export const DIRS4: Point[] = [
	[1, 0],
	[-1, 0],
	[0, 1],
	[0, -1],
];
export const DIRS8: Point[] = [...DIRS4, [1, 1], [1, -1], [-1, 1], [-1, -1]];

export function carveRect(
	f: Floor,
	x0: number,
	y0: number,
	w: number,
	h: number,
	room: number,
) {
	for (let y = y0; y < y0 + h; y++)
		for (let x = x0; x < x0 + w; x++) {
			f.tiles[index(f, x, y)] = FLOOR;
			f.room[index(f, x, y)] = room;
		}
}

/** Floor cells, for placing things. */
export function floorCells(
	f: Floor,
	keep: (i: number) => boolean = () => true,
): Point[] {
	const out: Point[] = [];
	for (let i = 0; i < f.tiles.length; i++)
		if (f.tiles[i] === FLOOR && keep(i))
			out.push([i % f.w, Math.floor(i / f.w)]);
	return out;
}
