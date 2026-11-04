import { expect, test } from "bun:test";
import { buildAlias, sampleAlias } from "./reference";

/** The exact chance of each outcome, by integrating over the column and the coin. */
function exact(weights: number[]): number[] {
	const t = buildAlias(weights);
	const n = weights.length;
	const out = Array<number>(n).fill(0);
	for (let col = 0; col < n; col++) {
		out[col] = (out[col] as number) + (t.prob[col] as number) / n;
		const a = t.alias[col] as number;
		out[a] = (out[a] as number) + (1 - (t.prob[col] as number)) / n;
	}
	return out;
}

test("each outcome comes up in proportion to its weight", () => {
	for (const w of [[1, 2, 3, 2], [40, 30, 15, 9], [1, 1, 1], [5], [1, 100]]) {
		const total = w.reduce((a, b) => a + b, 0);
		exact(w).forEach((p, i) => {
			expect(p).toBeCloseTo((w[i] as number) / total, 10);
		});
	}
});

test("sampling picks a column and flips its coin", () => {
	const t = buildAlias([1, 3]);
	expect(t.prob[0]).toBeCloseTo(0.5);
	expect(t.alias[0]).toBe(1);
	expect(sampleAlias(t, 0.1, 0.4)).toBe(0);
	expect(sampleAlias(t, 0.1, 0.6)).toBe(1);
	expect(sampleAlias(t, 0.9, 0.99)).toBe(1);
});

test("weights must be positive", () => {
	expect(() => buildAlias([])).toThrow();
	expect(() => buildAlias([0, 0])).toThrow();
});
