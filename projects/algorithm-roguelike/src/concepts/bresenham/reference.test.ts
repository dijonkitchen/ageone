import { expect, test } from "bun:test";
import { Rng } from "../../core/rng";
import { line, lineProblem } from "./reference";

test("known lines", () => {
	expect(line(0, 0, 3, 0)).toEqual([
		[0, 0],
		[1, 0],
		[2, 0],
		[3, 0],
	]);
	// Ties (the true line exactly between two cells) round toward the far end.
	expect(line(0, 0, 4, 2)).toEqual([
		[0, 0],
		[1, 1],
		[2, 1],
		[3, 2],
		[4, 2],
	]);
	expect(line(0, 0, 6, 2)).toEqual([
		[0, 0],
		[1, 0],
		[2, 1],
		[3, 1],
		[4, 1],
		[5, 2],
		[6, 2],
	]);
	expect(line(2, 2, 2, 2)).toEqual([[2, 2]]);
});

test("every reference line passes the checker, in every direction", () => {
	const rng = new Rng(3);
	for (let k = 0; k < 500; k++) {
		const [a, b, c, d] = [rng.int(50), rng.int(50), rng.int(50), rng.int(50)];
		expect(lineProblem(line(a, b, c, d), a, b, c, d)).toBeNull();
	}
});

test("the checker rejects bad lines", () => {
	expect(lineProblem([[0, 0]], 0, 0, 2, 0)).toContain("expected 3 cells");
	expect(
		lineProblem(
			[
				[0, 0],
				[2, 0],
				[2, 0],
			],
			0,
			0,
			2,
			0,
		),
	).toContain("not one step");
	expect(
		lineProblem(
			[
				[0, 0],
				[1, 1],
				[2, 1],
				[3, 0],
			],
			0,
			0,
			3,
			0,
		),
	).toContain("off the true line");
	expect(lineProblem("nope", 0, 0, 1, 1)).toContain("[x, y]");
});
