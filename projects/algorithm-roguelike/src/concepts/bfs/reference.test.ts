import { expect, test } from "bun:test";
import { bfs, bfsTrace } from "./reference";

test("distances around a wall, and -1 where unreachable", () => {
	expect(bfs(["..#.", ".##.", "...#"], [0, 0])).toEqual([
		[0, 1, -1, -1],
		[1, -1, -1, -1],
		[2, 3, 4, -1],
	]);
});

test("a start on a wall reaches nothing", () => {
	expect(bfs(["#."], [0, 0])).toEqual([[-1, -1]]);
});

test("the trace visits cells in order of distance, and agrees with bfs", () => {
	const grid = [".....", ".#.#.", "....."];
	const dist = bfs(grid, [2, 1]);
	const trace = bfsTrace(grid, [2, 1]);
	let last = 0;
	for (const t of trace) {
		expect(t.dist).toBeGreaterThanOrEqual(last);
		last = t.dist;
		expect(dist[t.cell[1]]?.[t.cell[0]]).toBe(t.dist);
	}
	expect(trace.length).toBe(13);
});
