import {
	carveRect,
	emptyFloor,
	FLOOR,
	index,
	type Point,
	SHRINE,
	STAIRS,
} from "../../core/grid";
import { Rng } from "../../core/rng";
import type { Concept, Ctx, Frame, Generated } from "../../core/types";
import { choice } from "../util";
import { neighbors, toIndex, toPoint } from "./reference";

const W = 46;
const H = 19;

/** Rooms on a 3 by 2 grid of cells, joined in a loop by L-shaped corridors. */
export function roomsOnAGrid(ctx: Ctx): Generated {
	const { rng } = ctx;
	const f = emptyFloor(W, H);
	const rooms: { x: number; y: number; w: number; h: number }[] = [];
	for (const [cx, cy] of [
		[0, 0],
		[1, 0],
		[2, 0],
		[2, 1],
		[1, 1],
		[0, 1],
	] as Point[]) {
		const w = rng.range(5, 11);
		const h = rng.range(3, 5);
		const x = cx * 15 + 1 + rng.int(14 - w);
		const y = cy * 9 + 1 + rng.int(8 - h);
		rooms.push({ x, y, w, h });
		carveRect(f, x, y, w, h, rooms.length - 1);
	}
	const centre = (r: { x: number; y: number; w: number; h: number }): Point => [
		r.x + (r.w >> 1),
		r.y + (r.h >> 1),
	];
	const dig = (x: number, y: number) => {
		const i = index(f, x, y);
		if (f.tiles[i] !== FLOOR) f.tiles[i] = FLOOR;
	};
	for (let i = 0; i < rooms.length; i++) {
		const [ax, ay] = centre(rooms[i] as (typeof rooms)[0]);
		const [bx, by] = centre(rooms[(i + 1) % rooms.length] as (typeof rooms)[0]);
		for (let x = Math.min(ax, bx); x <= Math.max(ax, bx); x++) dig(x, ay);
		for (let y = Math.min(ay, by); y <= Math.max(ay, by); y++) dig(bx, y);
	}
	const [start, shrine, stairs] = rng.shuffle([0, 1, 2, 3, 4, 5]) as [
		number,
		number,
		number,
	];
	const at = (r: number) => rooms[r] as (typeof rooms)[0];
	const [sx, sy] = centre(at(shrine));
	f.tiles[index(f, sx, sy)] = SHRINE;
	f.shrineRoom = shrine;
	const st = at(stairs);
	f.tiles[index(f, st.x + rng.int(st.w), st.y + rng.int(st.h))] = STAIRS;
	return { floor: f, start: centre(at(start)) };
}

function frames(seed: number): Frame[] {
	const rng = new Rng(seed);
	const w = 6;
	const h = 4;
	const cell = (i: number, mark: Set<number>) =>
		mark.has(i) ? `[${String(i).padStart(2)}]` : ` ${String(i).padStart(2)} `;
	const picture = (mark: Set<number>) =>
		Array.from({ length: h }, (_, y) =>
			Array.from({ length: w }, (_, x) => cell(toIndex(w, x, y), mark)).join(
				"",
			),
		);
	const out: Frame[] = [
		{
			caption: `A grid ${w} wide and ${h} tall is one array of ${w * h} cells, row after row.`,
			lines: picture(new Set()),
			data: [
				`cells = [${Array.from({ length: w * h }, (_, i) => i).join(", ")}]`,
			],
		},
	];
	for (let k = 0; k < 3; k++) {
		const x = rng.int(w);
		const y = rng.int(h);
		const i = toIndex(w, x, y);
		out.push({
			caption: `(${x}, ${y}) is row ${y}, column ${x}: index ${y} × ${w} + ${x} = ${i}.`,
			lines: picture(new Set([i])),
			data: [
				`index = y * width + x = ${i}`,
				`back again: x = ${i} % ${w} = ${toPoint(w, i)[0]}, y = floor(${i} / ${w}) = ${toPoint(w, i)[1]}`,
			],
		});
		const n = neighbors(w, h, i);
		out.push({
			caption: `Its neighbors are one step along the array (±1) or one row away (±${w}), if they stay inside the grid.`,
			lines: picture(new Set(n)),
			data: [`neighbors(${i}) = [${n.join(", ")}]`],
		});
	}
	return out;
}

export const concept: Concept = {
	id: "grid",
	name: "Arrays and 2D grids",
	tier: 1,
	requires: [],
	unlocks:
		"the map grows from one room to a floor of rooms joined by corridors.",
	complexity: {
		time: "O(1) to read or write a cell",
		space: "O(width × height)",
	},
	reading: {
		title: "Row- and column-major order (Wikipedia)",
		url: "https://en.wikipedia.org/wiki/Row-_and_column-major_order",
	},
	lesson: {
		text: [
			"An array is a row of numbered boxes. Box i is found straight away, without looking through the others, because the computer works out where it is from i.",
			"A dungeon floor is a 2D grid, but it is stored as one array: the first row, then the second, and so on. This is called row-major order.",
			"So the cell in column x of row y is at index y × width + x. Going back, x is the index modulo the width, and y is the index divided by the width, rounded down.",
			"A cell's neighbors are one box away on either side (±1) or one whole row away (±width). Watch the edges: the cell left of column 0 is not in this row.",
			"Every floor in this game, every field of view, and every path is built on this one idea.",
		],
		frames,
	},
	puzzle(seed) {
		const rng = new Rng(seed);
		const steps = [];
		for (let k = 0; k < 3; k++) {
			const w = rng.range(5, 12);
			const h = rng.range(4, 8);
			const x = rng.int(w);
			const y = rng.int(h);
			const i = toIndex(w, x, y);
			steps.push(
				choice(
					rng,
					`A grid is ${w} wide and ${h} tall. Which index holds the cell at x = ${x}, y = ${y}?`,
					String(i),
					[
						String(x * w + y),
						String(y * h + x),
						String(i + 1),
						String(x * h + y),
						String(i - w),
					],
					`Rows come first: ${y} full row${y === 1 ? "" : "s"} of ${w} cells, then ${x} more: ${y} × ${w} + ${x} = ${i}.`,
				),
			);
			const j = rng.int(w * h);
			const [jx, jy] = toPoint(w, j);
			steps.push(
				choice(
					rng,
					`In the same grid, which cell is index ${j}?`,
					`(${jx}, ${jy})`,
					[
						`(${jy}, ${jx})`,
						`(${j % h}, ${Math.floor(j / h)})`,
						`(${jx + 1}, ${jy})`,
						`(${jx}, ${jy + 1})`,
					],
					`x = ${j} % ${w} = ${jx}, y = floor(${j} / ${w}) = ${jy}.`,
				),
			);
		}
		const w = rng.range(6, 10);
		const i = w + 1 + rng.int(w - 2);
		steps.push(
			choice(
				rng,
				`A grid is ${w} wide. Which index is just below index ${i}?`,
				String(i + w),
				[String(i + 1), String(i - w), String(i + w + 1), String(i * 2)],
				`One row down is one whole row along the array: ${i} + ${w}.`,
			),
		);
		return {
			intro: "Find cells in a flat array, the way the game finds every tile.",
			steps,
			slack: 2,
		};
	},
	hooks: { generator: { priority: 1, generate: (ctx) => roomsOnAGrid(ctx) } },
};
