import { expect, test } from "bun:test";
import { fov } from "./reference";

const at = (w: number, x: number, y: number) => y * w + x;

test("an open room is all visible within the radius, walls included", () => {
	const grid = ["#######", "#.....#", "#.....#", "#.....#", "#######"];
	const seen = new Set(fov(grid, 3, 2, 8));
	for (let y = 0; y < 5; y++)
		for (let x = 0; x < 7; x++) expect(seen.has(at(7, x, y))).toBe(true);
});

test("a pillar casts a shadow behind it", () => {
	const grid = [".........", "....#....", ".........", "........."];
	const seen = new Set(fov(grid, 4, 3, 8));
	expect(seen.has(at(9, 4, 1))).toBe(true); // the pillar itself
	expect(seen.has(at(9, 4, 0))).toBe(false); // straight behind it
	expect(seen.has(at(9, 0, 0))).toBe(true);
});

test("the radius limits the view, and the viewer sees its own cell", () => {
	const grid = [".".repeat(30)];
	const seen = fov(grid, 0, 0, 5);
	expect(seen).toEqual([0, 1, 2, 3, 4, 5]);
});
