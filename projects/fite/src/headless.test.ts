import { expect, test } from "bun:test";
import { Cpu, LEVELS, PROFILES } from "./cpu";
import { FIGHTERS, fighter } from "./fighters";
import { simulate } from "./headless";
import { newMatch, step } from "./sim";

test("hard beats easy in most of 50 simulated matches", () => {
	let hard = 0;
	for (let i = 0; i < 50; i++) {
		const a = FIGHTERS[i % FIGHTERS.length];
		const b = FIGHTERS[(i * 3 + 1) % FIGHTERS.length];
		if (!a || !b) throw new Error("roster");
		// Alternate sides so neither starting position decides it.
		const hardFirst = i % 2 === 0;
		const o = simulate(
			{ fighter: a, level: hardFirst ? "hard" : "easy" },
			{ fighter: b, level: hardFirst ? "easy" : "hard" },
			i,
		);
		if (o.result === (hardFirst ? 0 : 1)) hard++;
	}
	expect(hard).toBeGreaterThan(25);
});

test("every pairing plays thousands of frames with the state staying sane", () => {
	let frames = 0;
	for (const [i, a] of FIGHTERS.entries())
		for (const [j, b] of FIGHTERS.entries()) {
			const level = LEVELS[(i + j) % LEVELS.length] ?? "normal";
			const o = simulate(
				{ fighter: a, level },
				{ fighter: b, level: "normal" },
				i * 10 + j,
			);
			expect([0, 1, "draw"]).toContain(o.result);
			expect(o.hits).toBeGreaterThan(0);
			frames += o.frames;
		}
	expect(frames).toBeGreaterThan(10_000);
});

test("simulations replay exactly from their seed", () => {
	const p = { fighter: fighter("zip"), level: "normal" as const };
	const q = { fighter: fighter("reed"), level: "hard" as const };
	expect(simulate(p, q, 7)).toEqual(simulate(p, q, 7));
});

test("levels differ only in reaction and choices, and harder blocks more", () => {
	const keys = Object.keys(PROFILES.easy).sort();
	expect(keys).toEqual([
		"aggression",
		"antiAir",
		"block",
		"guard",
		"reaction",
		"special",
		"think",
	]);
	expect(PROFILES.hard.reaction).toBeLessThan(PROFILES.easy.reaction);
	expect(PROFILES.hard.block).toBeGreaterThan(PROFILES.easy.block);
	const blocks = (level: "easy" | "hard") => {
		let n = 0;
		for (let i = 0; i < 6; i++) {
			const o = simulate(
				{ fighter: fighter("kame"), level: "normal" },
				{ fighter: fighter("kame"), level },
				i,
			);
			n += o.blocks;
		}
		return n;
	};
	expect(blocks("hard")).toBeGreaterThan(blocks("easy"));
});

test("the CPU plays only through the input bitmask", () => {
	const m = newMatch(fighter("kame"), fighter("kame"));
	const cpu = new Cpu("hard", 1);
	for (let i = 0; i < 600; i++) {
		const input = cpu.input(m, 1);
		expect(Number.isInteger(input) && input >= 0 && input < 256).toBe(true);
		step(m, [0, input]);
	}
});
