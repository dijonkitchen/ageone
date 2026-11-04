import { expect, test } from "bun:test";
import { lcg, mulberry32, sequence } from "./reference";

test("the teaching LCG has full period 16", () => {
	expect(new Set(sequence(lcg(5, 3, 16), 0, 16)).size).toBe(16);
	expect(sequence(lcg(5, 3, 16), 7, 3)).toEqual([6, 1, 8]);
});

test("mulberry32 is a pure function of its state", () => {
	const [s1, f1] = mulberry32(42);
	expect(mulberry32(42)).toEqual([s1, f1]);
	expect(f1).toBeGreaterThanOrEqual(0);
	expect(f1).toBeLessThan(1);
	let s = 1;
	const seen = new Set<number>();
	for (let i = 0; i < 1000; i++) {
		const [n, f] = mulberry32(s);
		seen.add(Math.floor(f * 10));
		s = n;
	}
	expect(seen.size).toBe(10);
});
