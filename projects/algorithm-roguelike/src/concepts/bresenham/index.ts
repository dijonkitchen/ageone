import { hurtMonster, monsterAt, removeOne, say } from "../../core/engine";
import {
	emptyFloor,
	index,
	type Point,
	passable,
	tileAt,
} from "../../core/grid";
import { Rng } from "../../core/rng";
import type {
	CodeTrial,
	Concept,
	Frame,
	PuzzleStep,
	TestCase,
} from "../../core/types";
import { choice, draw, xy } from "../util";
import { line, lineProblem } from "./reference";

const validLine = (r: unknown) =>
	Array.isArray(r) &&
	r.length > 0 &&
	r.every((c) => Array.isArray(c) && c.length === 2);

function lineFrames(a: Point, b: Point, w = 16, h = 9): Frame[] {
	const f = emptyFloor(w, h);
	const blank = { ...f, tiles: f.tiles.map(() => "·") };
	const cells = line(a[0], a[1], b[0], b[1]);
	const dx = Math.abs(b[0] - a[0]);
	const dy = -Math.abs(b[1] - a[1]);
	let err = dx + dy;
	return cells.map((c, k) => {
		const marks = new Map<number, string>(
			cells.slice(0, k + 1).map(([x, y]) => [index(f, x, y), "*"]),
		);
		marks.set(index(f, b[0], b[1]), k === cells.length - 1 ? "*" : "B");
		marks.set(index(f, a[0], a[1]), "A");
		const frame = {
			caption: `Cell ${k + 1}: ${xy(c)}. The error term says whether to step across, up or down, or both.`,
			lines: draw(blank, marks),
			data: [
				`dx = ${dx}, dy = ${dy}, error = ${err}`,
				`2 × error = ${2 * err}: ${2 * err >= dy ? "step in x" : ""}${2 * err >= dy && 2 * err <= dx ? " and " : ""}${2 * err <= dx ? "step in y" : ""}`,
			],
		};
		const e2 = 2 * err;
		if (e2 >= dy) err += dy;
		if (e2 <= dx) err += dx;
		return frame;
	});
}

function suite(): TestCase[] {
	const rng = new Rng(77);
	const cases: [string, number, number, number, number][] = [
		["a single cell", 3, 3, 3, 3],
		["flat to the right", 0, 0, 7, 0],
		["straight up", 2, 9, 2, 1],
		["a perfect diagonal", 0, 0, 5, 5],
		["shallow, going right", 0, 0, 9, 3],
		["steep, going down", 1, 1, 3, 10],
		["going left and up", 10, 8, 1, 4],
		["steep, going left and down", 6, 0, 4, 9],
	];
	for (let k = 0; k < 24; k++)
		cases.push([
			`random line ${k + 1}`,
			rng.int(46),
			rng.int(19),
			rng.int(46),
			rng.int(19),
		]);
	return cases.map(([name, x0, y0, x1, y1]) => ({
		name: `${name}: (${x0},${y0}) to (${x1},${y1})`,
		run: (call) => lineProblem(call("line", x0, y0, x1, y1), x0, y0, x1, y1),
	}));
}

const trial: CodeTrial = {
	exports: ["line"],
	docs: [
		"Write line(x0, y0, x1, y1).",
		"Return the grid cells from (x0, y0) to (x1, y1), both included, as [[x, y], ...].",
		"Each cell must be one step (straight or diagonal) from the one before, there must be max(|x1 - x0|, |y1 - y0|) + 1 of them, and each must be within half a cell of the true line.",
		"Bresenham's algorithm does this with whole numbers only. Any line that meets the rules passes.",
		"In the game your line aims thrown darts (t): the dart flies along it until it hits a wall or a monster.",
	].join("\n"),
	starter: [
		"function line(x0, y0, x1, y1) {",
		"  const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0);",
		"  const sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;",
		"  let err = dx + dy, x = x0, y = y0;",
		"  const cells = [];",
		"  // Add [x, y]; stop at the end; otherwise use 2 * err to decide",
		"  // whether to step in x, in y, or in both, updating err as you go.",
		"  return cells;",
		"}",
	].join("\n"),
	suite: suite(),
	budgetMs: 1500,
	reference: { line },
};

export const concept: Concept = {
	id: "bresenham",
	name: "Bresenham lines",
	tier: 2,
	requires: ["grid"],
	unlocks:
		"throw darts (t) at the nearest monster in sight; walls block the throw.",
	complexity: {
		time: "O(n) for a line n cells long",
		space: "O(1) beyond the cells",
	},
	reading: {
		title: "Bresenham's line algorithm (Wikipedia)",
		url: "https://en.wikipedia.org/wiki/Bresenham%27s_line_algorithm",
	},
	lesson: {
		text: [
			"A straight line on a grid has to pick which cells to fill. Bresenham's algorithm walks from one end to the other one cell at a time and chooses the cells nearest the true line.",
			"It keeps an error term: how far the cells so far have drifted from the true line. Each step it moves along the long axis, and also along the short axis when the error says it has drifted half a cell or more.",
			"It uses only whole-number adds and compares, so it was fast on the earliest computers and is still the standard way to draw lines and trace shots on a grid.",
			"In the game a thrown dart flies along this line, stopping at the first wall or monster it meets.",
		],
		frames: (seed) => {
			const rng = new Rng(seed);
			return lineFrames([1, 1 + rng.int(3)], [13 + rng.int(2), 4 + rng.int(4)]);
		},
	},
	puzzle(seed) {
		const rng = new Rng(seed);
		const a: Point = [1, 1 + rng.int(2)];
		const b: Point = [11 + rng.int(4), 3 + rng.int(5)];
		const cells = line(a[0], a[1], b[0], b[1]);
		const f = emptyFloor(16, 9);
		const blank = { ...f, tiles: f.tiles.map(() => "·") };
		const steps: PuzzleStep[] = [];
		for (let k = 1; k < cells.length && steps.length < 6; k += 2) {
			const prev = cells[k - 1] as Point;
			const marks = new Map<number, string>(
				cells.slice(0, k).map(([x, y]) => [index(f, x, y), "*"]),
			);
			marks.set(index(f, a[0], a[1]), "A");
			marks.set(index(f, b[0], b[1]), "B");
			const sx = Math.sign(b[0] - a[0]);
			const sy = Math.sign(b[1] - a[1]);
			const options = [
				xy([prev[0] + sx, prev[1]]),
				xy([prev[0] + sx, prev[1] + sy]),
				xy([prev[0], prev[1] + sy]),
			];
			const answer = xy(cells[k] as Point);
			steps.push(
				choice(
					rng,
					`The line from A ${xy(a)} to B ${xy(b)} has reached ${xy(prev)}. Which cell comes next?`,
					answer,
					options,
					`The true line passes nearest ${answer}: the error term ${answer === options[1] ? "has drifted half a cell, so it steps in both x and y" : "has not drifted half a cell, so it steps only along the long axis"}.`,
					draw(blank, marks),
				),
			);
		}
		steps.push(
			choice(
				rng,
				`How many cells does the line from ${xy(a)} to ${xy(b)} fill?`,
				String(cells.length),
				[
					String(cells.length - 1),
					String(cells.length + 1),
					String(Math.abs(b[0] - a[0]) + Math.abs(b[1] - a[1]) + 1),
				],
				"One cell per step along the long axis, plus the first: max(|dx|, |dy|) + 1.",
			),
		);
		return {
			intro: "Choose the cells of a line, step by step.",
			steps,
			slack: 2,
		};
	},
	hooks: {
		actions: {
			throw: {
				key: "t",
				label: "Throw a dart at the nearest monster in sight",
				run(ctx, s) {
					const slot = s.inventory.findIndex((st) => st.kind === "dart");
					if (slot < 0) {
						say(s, "You have no darts.");
						return false;
					}
					const seen = new Set(s.visible);
					const { x, y } = s.player;
					const targets = s.monsters
						.filter((m) => seen.has(index(s.floor, m.x, m.y)))
						.sort(
							(a, b) =>
								Math.max(Math.abs(a.x - x), Math.abs(a.y - y)) -
									Math.max(Math.abs(b.x - x), Math.abs(b.y - y)) || a.id - b.id,
						);
					const target = targets[0];
					if (!target) {
						say(s, "No monster in sight to throw at.");
						return false;
					}
					removeOne(s, slot);
					const path = ctx.code("line", line, validLine)(
						x,
						y,
						target.x,
						target.y,
					);
					let land: Point = [x, y];
					for (const [cx, cy] of path.slice(1)) {
						if (!passable(tileAt(s.floor, cx, cy))) {
							say(s, "The dart hits a wall.");
							break;
						}
						land = [cx, cy];
						const m = monsterAt(s, cx, cy);
						if (m) {
							hurtMonster(s, m, ctx.rng.range(2, 4), `throw a dart at`);
							break;
						}
					}
					s.items.push({ x: land[0], y: land[1], kind: "dart" });
					return true;
				},
			},
		},
	},
	code: trial,
	sandbox(floor, from) {
		const out: Frame[] = [];
		const targets = floor.tiles
			.flatMap((t, i) =>
				t === "." && i % 37 === 0
					? [[i % floor.w, Math.floor(i / floor.w)] as Point]
					: [],
			)
			.slice(0, 12);
		for (const to of targets) {
			const cells = line(from[0], from[1], to[0], to[1]);
			const marks = new Map<number, string>();
			let blocked = false;
			for (const [x, y] of cells.slice(1)) {
				if (floor.tiles[index(floor, x, y)] === "#") blocked = true;
				marks.set(index(floor, x, y), blocked ? "x" : "*");
			}
			marks.set(index(floor, from[0], from[1]), "@");
			out.push({
				caption: `A line from ${xy(from)} to ${xy(to)}${blocked ? ": a wall blocks it (x)" : ": clear"}.`,
				lines: draw(floor, marks),
				data: [`${cells.length} cells`],
			});
		}
		return out;
	},
};
