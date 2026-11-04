import { expect, test } from "bun:test";
import { Rng } from "../../core/rng";
import { bfs } from "../bfs/reference";
import { dfsOrder, drunkardsWalk } from "./reference";

test("DFS goes deep before wide", () => {
	const g = { A: ["B", "C"], B: ["D"], C: ["E"], D: [], E: [] };
	expect(dfsOrder(g, "A").map((t) => t.node)).toEqual([
		"A",
		"B",
		"D",
		"C",
		"E",
	]);
});

test("a drunkard's walk carves the coverage asked for, all connected, inside the border", () => {
	for (const seed of [1, 2, 3]) {
		const { open } = drunkardsWalk(30, 15, 0.4, new Rng(seed));
		const carved = open.filter(Boolean).length;
		expect(carved).toBe(Math.floor(28 * 13 * 0.4));
		const rows = Array.from({ length: 15 }, (_, y) =>
			Array.from({ length: 30 }, (_, x) => (open[y * 30 + x] ? "." : "#")).join(
				"",
			),
		);
		expect(rows[0]).toBe("#".repeat(30));
		const dist = bfs(rows, [15, 7]);
		expect(
			open.every(
				(o, i) => !o || (dist[Math.floor(i / 30)]?.[i % 30] ?? -1) >= 0,
			),
		).toBe(true);
	}
});
