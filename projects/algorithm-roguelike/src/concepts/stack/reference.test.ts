import { expect, test } from "bun:test";
import { Stack } from "./reference";

test("last in, first out", () => {
	const s = new Stack<number>();
	for (const v of [1, 2, 3]) s.push(v);
	expect(s.peek()).toBe(3);
	expect([s.pop(), s.pop(), s.pop(), s.pop()]).toEqual([3, 2, 1, undefined]);
	expect(s.size).toBe(0);
});

test("a bounded stack drops its oldest entries", () => {
	const s = new Stack<number>(2);
	for (const v of [1, 2, 3]) s.push(v);
	expect(s.toArray()).toEqual([2, 3]);
});
