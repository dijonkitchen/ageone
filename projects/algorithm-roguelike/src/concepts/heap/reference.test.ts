import { expect, test } from "bun:test";
import { Rng } from "../../core/rng";
import {
	heapPop,
	heapPush,
	isHeap,
	popInPlace,
	pushInPlace,
} from "./reference";

test("pops come out sorted, with ties broken by later items", () => {
	const rng = new Rng(9);
	let h: number[][] = [];
	const items = Array.from({ length: 200 }, (_, i) => [rng.int(20), i]);
	for (const it of items) {
		h = heapPush(h, it);
		expect(isHeap(h)).toBe(true);
	}
	const out: number[][] = [];
	for (;;) {
		const [e, rest] = heapPop(h);
		if (!e) break;
		out.push(e);
		h = rest;
		expect(isHeap(h)).toBe(true);
	}
	expect(out).toEqual(
		[...items].sort(
			(a, b) =>
				(a[0] as number) - (b[0] as number) ||
				(a[1] as number) - (b[1] as number),
		),
	);
});

test("push and pop don't change the heap they are given", () => {
	const h = heapPush(heapPush([], [3]), [1]);
	const copy = JSON.stringify(h);
	heapPush(h, [0]);
	heapPop(h);
	expect(JSON.stringify(h)).toBe(copy);
	expect(heapPop([])).toEqual([null, []]);
});

test("the in-place versions agree with the pure ones", () => {
	const rng = new Rng(4);
	let pure: number[][] = [];
	const mut: number[][] = [];
	for (let i = 0; i < 100; i++) {
		const e = [rng.int(10), i];
		pure = heapPush(pure, e);
		pushInPlace(mut, e);
	}
	expect(mut).toEqual(pure);
	for (let i = 0; i < 100; i++) {
		const [e, rest] = heapPop(pure);
		pure = rest;
		expect(popInPlace(mut)).toEqual(e as number[]);
	}
	expect(popInPlace(mut)).toBeUndefined();
});
