import { describe, expect, test } from "bun:test";
import {
	band,
	bounds,
	ellipse,
	longBone,
	mirrorPath,
	pathPoints,
	polygon,
	rotate,
	smooth,
} from "./geometry";

describe("geometry", () => {
	test("smooth curves pass through their points and close", () => {
		const pts: [number, number][] = [
			[0, 0],
			[10, 0],
			[10, 10],
			[0, 10],
		];
		const d = smooth(pts);
		expect(d.startsWith("M0 0")).toBe(true);
		expect(d.endsWith("Z")).toBe(true);
		for (const p of pts) expect(d).toContain(`${p[0]} ${p[1]}`);
		expect(() => smooth(pts.slice(0, 2))).toThrow();
	});

	test("mirroring flips x, and twice gives the path back", () => {
		for (const d of [
			polygon([
				[1, 2],
				[3, 4],
				[5, 7],
			]),
			ellipse([4, 5], 2, 3),
			smooth([
				[1, 1],
				[4, 2],
				[2, 6],
			]),
		]) {
			const once = mirrorPath(d);
			expect(pathPoints(once)).toEqual(
				pathPoints(d).map(([x, y]) => [-x === 0 ? 0 : -x, y]),
			);
			expect(pathPoints(mirrorPath(once))).toEqual(pathPoints(d));
		}
	});

	test("bands and long bones stay near their centreline", () => {
		const b = bounds(
			pathPoints(
				band(
					[
						[0, 0],
						[0, 20],
					],
					4,
				),
			),
		);
		expect(b.w).toBeLessThan(8);
		expect(b.h).toBeGreaterThanOrEqual(20);
		const bone = bounds(pathPoints(longBone([0, 0], [0, 40], 2, 3, 3)));
		expect(bone.y).toBeLessThan(0);
		expect(bone.y + bone.h).toBeGreaterThan(40);
		expect(bone.w).toBeLessThan(10);
	});

	test("rotate turns clockwise on screen about a centre", () => {
		const [x, y] = rotate([1, 0], 90, [0, 0]);
		expect(x).toBeCloseTo(0);
		expect(y).toBeCloseTo(1);
		expect(rotate([5, 5], 45, [5, 5])).toEqual([5, 5]);
	});
});
