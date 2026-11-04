import { expect, test } from "bun:test";
import { neighbors, toIndex, toPoint } from "./reference";

test("indices and points round-trip in row-major order", () => {
	for (let y = 0; y < 5; y++)
		for (let x = 0; x < 7; x++)
			expect(toPoint(7, toIndex(7, x, y))).toEqual([x, y]);
	expect(toIndex(7, 3, 2)).toBe(17);
});

test("neighbors stay inside the grid", () => {
	expect(neighbors(4, 3, 0).sort((a, b) => a - b)).toEqual([1, 4]);
	expect(neighbors(4, 3, 3).sort((a, b) => a - b)).toEqual([2, 7]);
	expect(neighbors(4, 3, 5).sort((a, b) => a - b)).toEqual([1, 4, 6, 9]);
	expect(neighbors(4, 3, 4)).not.toContain(3); // the left edge doesn't wrap to the row above
});
