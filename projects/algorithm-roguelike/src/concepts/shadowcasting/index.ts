import { index, type Point, rows } from "../../core/grid";
import { Rng } from "../../core/rng";
import type { Concept, Frame, PuzzleStep } from "../../core/types";
import { choice, draw, mapOf, xy } from "../util";
import { fov, fovByOctant } from "./reference";

const RADIUS = 8;
const DEMO = [
	"###################",
	"#.................#",
	"#....#......#.....#",
	"#.........##......#",
	"#..#..............#",
	"#.......#.....#...#",
	"#...........#.....#",
	"###################",
];

function octantFrames(grid: string[], from: Point, radius: number): Frame[] {
	const f = mapOf(grid);
	const lit = new Set<number>([index(f, from[0], from[1])]);
	return fovByOctant(grid, from[0], from[1], radius).map((cells, k) => {
		for (const c of cells) lit.add(c);
		const marks = new Map<number, string>();
		for (let i = 0; i < f.tiles.length; i++)
			marks.set(i, lit.has(i) ? (f.tiles[i] === "#" ? "#" : "·") : " ");
		marks.set(index(f, from[0], from[1]), "@");
		return {
			caption: `Octant ${k + 1} of 8 scanned: walls cast shadows, and the scan skips the slopes they hide.`,
			lines: draw(f, marks),
			data: [
				`visible so far: ${lit.size} cells`,
				`this octant: ${cells.length}`,
			],
		};
	});
}

export const concept: Concept = {
	id: "shadowcasting",
	name: "Recursive shadowcasting",
	tier: 2,
	requires: ["bresenham"],
	unlocks:
		"a real field of view 8 cells deep, and fog of war: you remember what you have seen.",
	complexity: { time: "O(r²) cells for radius r", space: "O(r) recursion" },
	reading: {
		title: "FOV using recursive shadowcasting (RogueBasin)",
		url: "https://www.roguebasin.com/index.php/FOV_using_recursive_shadowcasting",
	},
	lesson: {
		text: [
			"Field of view asks which cells you can see. You could trace a Bresenham line to every cell, but that repeats work and leaves gaps.",
			"Shadowcasting splits the view around you into 8 slices (octants) and scans each one row by row, moving outward. It tracks the range of slopes still lit, from the start slope to the end slope.",
			"When the scan meets a wall, everything behind it, between the slopes the wall covers, is in shadow. The scan recurses on the lit part before the wall and carries on past it, so each cell is visited about once.",
			"Fog of war is the memory: cells you have seen stay drawn, dimmed, but monsters show only where you see them now.",
		],
		frames: () => octantFrames(DEMO, [9, 4], RADIUS),
	},
	puzzle(seed) {
		const rng = new Rng(seed);
		const from: Point = [rng.pick([3, 9, 15]), rng.pick([3, 4])];
		const f = mapOf(DEMO);
		const seen = new Set(fov(DEMO, from[0], from[1], RADIUS));
		const cells = rng.shuffle(
			f.tiles.flatMap((t, i) =>
				t === "." && i !== index(f, from[0], from[1]) ? [i] : [],
			),
		);
		const pickSome = (vis: boolean, n: number) =>
			cells.filter((i) => seen.has(i) === vis).slice(0, n);
		const steps: PuzzleStep[] = rng
			.shuffle([...pickSome(true, 3), ...pickSome(false, 3)])
			.map((i) => {
				const p: Point = [i % f.w, Math.floor(i / f.w)];
				const marks = new Map([
					[index(f, from[0], from[1]), "@"],
					[i, "X"],
				]);
				const vis = seen.has(i);
				return choice(
					rng,
					`Can @ see the cell marked X ${xy(p)}?`,
					vis ? "Visible" : "Hidden",
					[vis ? "Hidden" : "Visible"],
					vis
						? "No wall casts a shadow over X: some line of sight to it is clear."
						: "A wall between @ and X casts a shadow that covers X.",
					draw(f, marks),
					2,
				);
			});
		return { intro: "Say which cells the player can see.", steps, slack: 1 };
	},
	hooks: {
		vision: (_ctx, s) => fov(rows(s.floor), s.player.x, s.player.y, RADIUS),
		memory: true,
	},
	sandbox: (floor, from) => octantFrames(rows(floor), from, RADIUS),
};
