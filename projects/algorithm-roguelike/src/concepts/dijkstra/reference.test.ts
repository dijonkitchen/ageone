import { expect, test } from "bun:test";
import { dijkstraGraph, dijkstraMap, fleeMap } from "./reference";

test("with unit costs in an open room, distance is the king-move distance", () => {
	const grid = [".....", ".....", "....."];
	const d = dijkstraMap(grid, [[0, 0, 0]]);
	for (let y = 0; y < 3; y++)
		for (let x = 0; x < 5; x++) expect(d[y * 5 + x]).toBe(Math.max(x, y));
});

test("costly cells are routed around, walls are unreachable", () => {
	const grid = ["...", "#~.", "..."];
	const d = dijkstraMap(grid, [[0, 0, 0]], (x, y) =>
		grid[y]?.[x] === "~" ? 5 : 1,
	);
	expect(d[3]).toBe(Number.POSITIVE_INFINITY);
	expect(d[4]).toBe(5);
	expect(d[7]).toBe(3); // around through the right: (1,0) → (2,1) → (1,2)
});

test("settling order on a small graph", () => {
	const g = {
		A: [
			["B", 4],
			["C", 1],
		],
		B: [
			["A", 4],
			["C", 2],
			["D", 5],
		],
		C: [
			["A", 1],
			["B", 2],
			["D", 8],
		],
		D: [
			["B", 5],
			["C", 8],
		],
	} as Record<string, [string, number][]>;
	expect(dijkstraGraph(g, "A").map((t) => [t.node, t.dist])).toEqual([
		["A", 0],
		["C", 1],
		["B", 3],
		["D", 8],
	]);
});

test("a flee map points away from the source", () => {
	const grid = ["........"];
	const chase = dijkstraMap(grid, [[0, 0, 0]]);
	const flee = fleeMap(grid, chase);
	for (let x = 1; x < 8; x++)
		expect(flee[x] as number).toBeLessThan(flee[x - 1] as number);
});
