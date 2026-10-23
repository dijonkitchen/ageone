import { MONSTERS } from "../../core/engine";
import { Rng } from "../../core/rng";
import type {
	CodeTrial,
	Concept,
	Ctx,
	Frame,
	PuzzleStep,
	State,
	TestCase,
} from "../../core/types";
import { choice } from "../util";
import { heapPop, heapPush, isHeap } from "./reference";

/** The heap drawn as a tree, one level per line. */
export function tree(h: number[][]): string[] {
	const out: string[] = [];
	for (let start = 0, size = 1; start < h.length; start += size, size *= 2)
		out.push(
			h
				.slice(start, start + size)
				.map((e) => (e.length === 1 ? String(e[0]) : `[${e.join(",")}]`))
				.join("   "),
		);
	return out.length ? out : ["(empty)"];
}

const flat = (h: number[][]) => `[${h.map((e) => e[0]).join(", ")}]`;

function frames(seed: number): Frame[] {
	const rng = new Rng(seed);
	let h: number[][] = [];
	const out: Frame[] = [];
	for (let k = 0; k < 7; k++) {
		const v = rng.range(1, 40);
		h = heapPush(h, [v]);
		out.push({
			caption: `Push ${v}: add it at the end, then swap it up while it is smaller than its parent.`,
			lines: tree(h),
			data: [`array: ${flat(h)}`],
		});
	}
	for (let k = 0; k < 3; k++) {
		const [top, rest] = heapPop(h);
		h = rest;
		out.push({
			caption: `Pop: take the root (${top?.[0]}), move the last entry to the root, and swap it down past its smaller child.`,
			lines: tree(h),
			data: [`popped ${top?.[0]}`, `array: ${flat(h)}`],
		});
	}
	return out;
}

const validPop = (r: unknown) =>
	Array.isArray(r) && r.length === 2 && Array.isArray(r[1]);
const validHeap = (r: unknown) =>
	Array.isArray(r) && r.every((e) => Array.isArray(e));

/** Speed-based turns: every actor waits in a heap keyed by the time of its next move. */
function afterPlayer(
	ctx: Ctx,
	s: State,
	act: (id: number) => void,
	cost: number,
) {
	const push = ctx.code("heapPush", heapPush, validHeap);
	const pop = ctx.code("heapPop", heapPop, validPop);
	if (!s.sched) {
		s.sched = [];
		for (const m of s.monsters)
			s.sched = push(s.sched, [
				s.time + 10000 / (MONSTERS[m.kind]?.speed ?? 100),
				s.seq++,
				m.id,
			]) as [number, number, number][];
	}
	s.sched = push(s.sched, [s.time + cost, s.seq++, 0]) as [
		number,
		number,
		number,
	][];
	for (let guard = 0; guard < 1000; guard++) {
		const [entry, rest] = pop(s.sched);
		s.sched = rest as [number, number, number][];
		if (!entry) return;
		const [time, , id] = entry as [number, number, number];
		s.time = time;
		if (id === 0) return;
		const m = s.monsters.find((x) => x.id === id);
		if (!m) continue;
		act(id);
		if (s.over) return;
		s.sched = push(s.sched, [
			time + 10000 / (MONSTERS[m.kind]?.speed ?? 100),
			s.seq++,
			id,
		]) as [number, number, number][];
	}
}

function suite(): TestCase[] {
	const rng = new Rng(5);
	const cases: TestCase[] = [
		{
			name: "popping an empty heap gives [null, []]",
			run: (call) =>
				JSON.stringify(call("heapPop", [])) === "[null,[]]"
					? null
					: `got ${JSON.stringify(call("heapPop", []))}`,
		},
		{
			name: "push one, pop it",
			run(call) {
				const h = call("heapPush", [], [7]);
				const r = call("heapPop", h) as [number[], number[][]];
				return JSON.stringify(r) === "[[7],[]]"
					? null
					: `got ${JSON.stringify(r)}`;
			},
		},
		{
			name: "entries compare item by item: [5, 2] before [5, 3] before [6, 0]",
			run(call) {
				let h: unknown = [];
				for (const e of [
					[6, 0],
					[5, 3],
					[5, 2],
				])
					h = call("heapPush", h, e);
				const order: unknown[] = [];
				for (let i = 0; i < 3; i++) {
					const [e, rest] = call("heapPop", h) as [unknown, unknown];
					order.push(e);
					h = rest;
				}
				return JSON.stringify(order) === "[[5,2],[5,3],[6,0]]"
					? null
					: `popped in the order ${JSON.stringify(order)}`;
			},
		},
	];
	for (const n of [10, 60, 250]) {
		const values = Array.from({ length: n }, (_, i) => [rng.int(100), i]);
		cases.push({
			name: `${n} pushes keep the heap property, then pops come out sorted`,
			run(call) {
				let h: number[][] = [];
				for (const v of values) {
					h = call("heapPush", h, v) as number[][];
					if (!Array.isArray(h) || !isHeap(h))
						return `after pushing ${JSON.stringify(v)} the array is not a heap: ${JSON.stringify(h).slice(0, 120)}`;
				}
				const out: number[][] = [];
				while (h.length) {
					const [e, rest] = call("heapPop", h) as [number[], number[][]];
					if (!isHeap(rest))
						return `after popping ${JSON.stringify(e)} the array is not a heap`;
					out.push(e);
					h = rest;
				}
				const want = [...values].sort(
					(a, b) =>
						(a[0] as number) - (b[0] as number) ||
						(a[1] as number) - (b[1] as number),
				);
				return JSON.stringify(out) === JSON.stringify(want)
					? null
					: "pops did not come out in sorted order";
			},
		});
	}
	return cases;
}

const trial: CodeTrial = {
	exports: ["heapPush", "heapPop"],
	docs: [
		"Write heapPush(heap, entry) and heapPop(heap) for a binary min-heap stored in an array.",
		"Entries are arrays of numbers, compared item by item: [5, 2] comes before [5, 3], which comes before [6, 0].",
		"heapPush returns the heap with the entry added; heapPop returns [smallest entry, the heap without it], or [null, []] when the heap is empty.",
		"The parent of index i is at Math.floor((i - 1) / 2); its children are at 2i + 1 and 2i + 2. No child may be smaller than its parent.",
		"In the game your heap runs the turn order: every creature waits in it, keyed by [time of its next move, a tie-breaker, its id].",
	].join("\n"),
	starter: [
		"function less(a, b) {",
		"  for (let k = 0; k < a.length; k++) if (a[k] !== b[k]) return a[k] < b[k];",
		"  return false;",
		"}",
		"",
		"function heapPush(heap, entry) {",
		"  const h = heap.concat([entry]);",
		"  // Swap the new entry up while it is less than its parent.",
		"  return h;",
		"}",
		"",
		"function heapPop(heap) {",
		"  if (heap.length === 0) return [null, []];",
		"  const h = heap.slice();",
		"  const top = h[0];",
		"  // Move the last entry to the root, then swap it down past its smaller child.",
		"  return [top, h];",
		"}",
	].join("\n"),
	suite: suite(),
	budgetMs: 3000,
	reference: { heapPush, heapPop },
};

export const concept: Concept = {
	id: "heap",
	name: "Priority queue (binary heap)",
	tier: 2,
	requires: ["grid"],
	unlocks:
		"speed-based turns: bats move twice for your once, zombies once for your two, and haste really is fast.",
	complexity: { time: "O(log n) push and pop; O(1) to peek", space: "O(n)" },
	reading: {
		title: "Binary heap (Wikipedia)",
		url: "https://en.wikipedia.org/wiki/Binary_heap",
	},
	lesson: {
		text: [
			"A priority queue hands back the smallest item first, whatever order items went in. The game uses one for turns: whoever's next move comes soonest goes next.",
			"A binary heap keeps it in an array shaped like a tree: index i's children are 2i + 1 and 2i + 2. The one rule is that no child is smaller than its parent, so the smallest is always at the root.",
			"Push adds the new item at the end and swaps it up while it is smaller than its parent. Pop takes the root, moves the last item to the root, and swaps it down past its smaller child.",
			"The tree is only log₂(n) levels deep, so both take O(log n) swaps, much faster than keeping a sorted list.",
			"In the game each creature waits in the heap until the time of its next move: a fast bat comes back after 50 ticks, a slow zombie after 200.",
		],
		frames,
	},
	puzzle(seed) {
		const rng = new Rng(seed);
		let h: number[][] = [];
		for (let k = 0; k < 6; k++) h = heapPush(h, [rng.range(1, 50)]);
		const steps: PuzzleStep[] = [];
		for (let k = 0; k < 6; k++) {
			if (k % 2 === 0) {
				let v = rng.range(1, 50);
				while (h.some((e) => e[0] === v)) v = rng.range(1, 50);
				const after = heapPush(h, [v]);
				const pos = after.findIndex((e) => e[0] === v);
				steps.push(
					choice(
						rng,
						`The heap array is ${flat(h)}. Push ${v}. At which index does ${v} end up?`,
						String(pos),
						Array.from({ length: after.length }, (_, i) => String(i)),
						`${v} starts at index ${h.length}, then swaps with its parent while it is smaller. The heap becomes ${flat(after)}.`,
						tree(h),
					),
				);
				h = after;
			} else {
				const [top, rest] = heapPop(h);
				steps.push(
					choice(
						rng,
						`The heap array is ${flat(h)}. Pop. What is the array afterwards?`,
						flat(rest),
						[
							flat(h.slice(1)),
							flat(
								[...rest].sort((a, b) => (a[0] as number) - (b[0] as number)),
							),
							flat([h.at(-1) as number[], ...h.slice(1, -1)]),
						],
						`Take the root ${top?.[0]}, move the last entry (${h.at(-1)?.[0]}) to the root, then swap it down past the smaller child until both children are bigger.`,
						tree(h),
					),
				);
				h = rest;
			}
		}
		return { intro: "Push and pop a binary heap by hand.", steps, slack: 2 };
	},
	hooks: { scheduler: { priority: 1, afterPlayer } },
	code: trial,
};
