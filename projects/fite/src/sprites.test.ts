import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fighter } from "./fighters";
import { pixels } from "./pixels";
import { decodePng, encodePng } from "./png";
import { newMatch, step } from "./sim";
import { CELL, POSE_NAMES, type PoseName, poseOf, sheet } from "./sprites";
import { drawStage, STAGES } from "./stage";

test("the sprite sheet drawn from code matches the committed sprites/sheet.png", () => {
	const committed = decodePng(
		readFileSync(join(import.meta.dir, "..", "sprites", "sheet.png")),
	);
	const drawn = sheet();
	expect([committed.width, committed.height]).toEqual([
		drawn.width,
		drawn.height,
	]);
	// Compare pixel by pixel; a failure names the first cell that differs. Fix it with `bun run sheet`.
	for (let i = 0; i < drawn.data.length; i++)
		if (drawn.data[i] !== committed.data[i]) {
			const px = Math.floor(i / 4);
			const x = px % drawn.width;
			const y = Math.floor(px / drawn.width);
			throw new Error(
				`sheet differs at pose ${POSE_NAMES[Math.floor(x / CELL)]}, row ${Math.floor(y / CELL)}: run \`bun run sheet\``,
			);
		}
});

test("every cell of the sheet has a drawn fighter", () => {
	const s = sheet();
	for (let row = 0; row < s.height / CELL; row++)
		for (let col = 0; col < POSE_NAMES.length; col++) {
			let filled = 0;
			for (let y = row * CELL; y < (row + 1) * CELL; y++)
				for (let x = col * CELL; x < (col + 1) * CELL; x++)
					if (s.data[(y * s.width + x) * 4 + 3]) filled++;
			expect(filled).toBeGreaterThan(150);
		}
});

test("PNGs round-trip", () => {
	const p = pixels(3, 2);
	p.data.set([
		1, 2, 3, 255, 4, 5, 6, 0, 7, 8, 9, 128, 10, 11, 12, 255, 0, 0, 0, 0, 255,
		255, 255, 255,
	]);
	expect(decodePng(encodePng(p))).toEqual(p);
});

test("stages are drawn edge to edge and differ from each other", () => {
	const drawn = STAGES.map((_, i) => drawStage(i));
	for (const s of drawn)
		for (let i = 3; i < s.data.length; i += 4) expect(s.data[i]).toBe(255);
	expect(new Set(drawn.map((s) => s.data.join(","))).size).toBe(STAGES.length);
});

test("a fight shows most poses", () => {
	const m = newMatch(fighter("kame"), fighter("zip"));
	const seen = new Set<PoseName>();
	const moves = [8, 0, 16, 32, 2, 2 | 32, 2 | 16, 1 | 8, 4, 64];
	for (let i = 0; i < 4000; i++) {
		m.fighters[0].meter = 100;
		step(m, [
			moves[Math.floor(i / 7) % moves.length] ?? 0,
			moves[Math.floor(i / 5) % moves.length] ?? 0,
		]);
		for (const f of m.fighters) seen.add(poseOf(f, m.frame));
	}
	expect(seen.size).toBeGreaterThan(POSE_NAMES.length - 5);
});
