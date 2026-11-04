// Helpers the concepts share for lessons, puzzles, and drawings.
import { emptyFloor, type Floor, index, type Point } from "../core/grid";
import type { Rng } from "../core/rng";
import type { PuzzleStep } from "../core/types";

/** A floor from rows of text ('#' walls, '.' floor). */
export function mapOf(rows: string[]): Floor {
	const h = rows.length;
	const w = Math.max(...rows.map((r) => r.length));
	const f = emptyFloor(w, h);
	for (let y = 0; y < h; y++)
		for (let x = 0; x < w; x++) f.tiles[index(f, x, y)] = rows[y]?.[x] ?? "#";
	return f;
}

/** Draw a floor's rows with some cells marked. */
export function draw(
	f: { w: number; h: number; tiles: string[] },
	marks: Map<number, string> = new Map(),
): string[] {
	const out: string[] = [];
	for (let y = 0; y < f.h; y++) {
		let line = "";
		for (let x = 0; x < f.w; x++) {
			const i = y * f.w + x;
			line += marks.get(i) ?? f.tiles[i] ?? " ";
		}
		out.push(line);
	}
	return out;
}

export const xy = ([x, y]: Point) => `(${x},${y})`;

/** A multiple-choice step whose answer comes from the reference; distractors are deduplicated and shuffled. */
export function choice(
	rng: Rng,
	prompt: string,
	answer: string,
	distractors: string[],
	explain: string,
	lines?: string[],
	max = 4,
): PuzzleStep {
	const others = [...new Set(distractors.filter((d) => d !== answer))];
	rng.shuffle(others);
	const choices = rng.shuffle([answer, ...others.slice(0, max - 1)]);
	return { prompt, choices, answer: choices.indexOf(answer), explain, lines };
}

/** Distance-digit drawing: 0-9 then letters, '+' beyond. */
export const digit = (d: number) =>
	d < 0 ? " " : d < 10 ? String(d) : d < 36 ? String.fromCharCode(87 + d) : "+";
