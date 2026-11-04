import { expect, test } from "bun:test";
import {
	allValid,
	BASE,
	balance,
	baseStats,
	baseTiles,
	generate,
	SET_SIZE,
	START,
	stats,
} from "./generate";

test("the base reference set has 72 tiles, 6 monasteries, and 10 shields", () => {
	expect(baseTiles()).toHaveLength(72);
	expect(Object.values(BASE).reduce((a, b) => a + b, 0)).toBe(72);
	expect(baseStats()).toMatchObject({ monasteries: 6, shields: 10 });
	expect(balance(baseTiles())).toEqual([]);
});

test("the same seed gives the same set, and different seeds different sets", () => {
	expect(generate(42)).toEqual(generate(42));
	expect(generate(42)).not.toEqual(generate(43));
});

test("every generated set has valid tiles and stays within the balance limits", () => {
	for (let seed = 1; seed <= 100; seed++) {
		const tiles = generate(seed);
		expect(tiles).toHaveLength(SET_SIZE);
		expect(tiles[0]).toBe(START);
		expect(allValid(tiles)).toBe(true);
		expect(balance(tiles)).toEqual([]);
	}
});

test("sets differ from the base set, not just reshuffle it", () => {
	const base = new Set(baseTiles());
	const novel = Array.from(
		{ length: 20 },
		(_, i) => generate(i + 1).filter((t) => !base.has(t)).length,
	);
	expect(novel.some((n) => n > 0)).toBe(true);
});

test("balance names what drifted", () => {
	const roads = Array<string>(72).fill("FRFR");
	const problems = balance(roads);
	expect(problems.some((p) => p.startsWith("C edge share"))).toBe(true);
	expect(problems.some((p) => p.startsWith("monasteries 0"))).toBe(true);
	expect(stats(roads).edges.R).toBe(0.5);
	expect(balance(roads.slice(1))[0]).toBe("71 tiles, not 72");
});
