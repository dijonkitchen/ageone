// Checks every concept folder against the contract in src/core/types.ts.
import { beforeAll, describe, expect, test } from "bun:test";
import type { QuickJSWASMModule } from "quickjs-emscripten-core";
import { grade, loadSandbox, PlayerCode, runSuite } from "../core/sandbox";
import { CONCEPTS } from "./index";

let qjs: QuickJSWASMModule;
beforeAll(async () => {
	qjs = await loadSandbox();
});

const byId = new Map(CONCEPTS.map((c) => [c.id, c]));

describe("the codex", () => {
	test("covers every tier 1 and tier 2 concept of the spec", () => {
		const want = {
			1: ["grid", "stack", "bfs", "hashmap", "prng"],
			2: [
				"randomwalk",
				"bresenham",
				"shadowcasting",
				"heap",
				"dijkstra",
				"alias",
			],
		};
		for (const [tier, ids] of Object.entries(want))
			for (const id of ids)
				expect(byId.get(id)?.tier).toBe(Number(tier) as 1 | 2);
		expect(new Set(CONCEPTS.map((c) => c.id)).size).toBe(CONCEPTS.length);
	});

	test("is a dependency graph with no cycles, and prerequisites never come from a later tier", () => {
		for (const c of CONCEPTS)
			for (const r of c.requires) {
				const req = byId.get(r);
				expect(req, `${c.id} needs ${r}`).toBeDefined();
				expect(req?.tier ?? 9).toBeLessThanOrEqual(c.tier);
			}
		const state = new Map<string, number>();
		const visit = (id: string): void => {
			expect(state.get(id), `cycle through ${id}`).not.toBe(1);
			if (state.get(id) === 2) return;
			state.set(id, 1);
			for (const r of byId.get(id)?.requires ?? []) visit(r);
			state.set(id, 2);
		};
		for (const c of CONCEPTS) visit(c.id);
		expect(CONCEPTS.filter((c) => !c.requires.length).map((c) => c.id)).toEqual(
			["grid"],
		);
	});
});

describe.each(CONCEPTS.map((c) => [c.id, c] as const))("%s", (_id, c) => {
	test("has its codex entry: effect, complexity, and further reading", () => {
		expect(c.name.length).toBeGreaterThan(2);
		expect(c.unlocks.length).toBeGreaterThan(10);
		expect(c.complexity.time).toBeTruthy();
		expect(c.complexity.space).toBeTruthy();
		expect(c.reading.url).toMatch(/^https:\/\//);
	});

	test("has a lesson: text and a step-through visualization", () => {
		expect(c.lesson.text.length).toBeGreaterThanOrEqual(3);
		for (const seed of [1, 2, 3]) {
			const frames = c.lesson.frames(seed);
			expect(frames.length).toBeGreaterThanOrEqual(3);
			for (const f of frames) {
				expect(f.caption.length).toBeGreaterThan(5);
				expect(f.lines.length).toBeGreaterThan(0);
			}
		}
	});

	test("has a puzzle-mode trial whose answers come from the reference, for any seed", () => {
		for (let seed = 1; seed <= 40; seed++) {
			const p = c.puzzle(seed);
			expect(p.steps.length).toBeGreaterThanOrEqual(3);
			expect(p.slack).toBeLessThan(p.steps.length);
			for (const s of p.steps) {
				expect(s.choices.length, s.prompt).toBeGreaterThanOrEqual(2);
				expect(new Set(s.choices).size).toBe(s.choices.length);
				expect(s.answer).toBeGreaterThanOrEqual(0);
				expect(s.answer).toBeLessThan(s.choices.length);
				expect(s.explain.length).toBeGreaterThan(5);
			}
		}
		expect(JSON.stringify(c.puzzle(7))).toBe(JSON.stringify(c.puzzle(7)));
	});

	test("plugs into the game through at least one hook", () => {
		expect(Object.keys(c.hooks).length).toBeGreaterThan(0);
	});
});

const coded = CONCEPTS.filter((c) => c.code);

test("at least three concepts, BFS and the heap among them, have a code-mode trial", () => {
	expect(coded.length).toBeGreaterThanOrEqual(3);
	expect(coded.map((c) => c.id)).toEqual(
		expect.arrayContaining(["bfs", "heap"]),
	);
});

describe.each(coded.map((c) => [c.id, c] as const))(
	"code mode: %s",
	(_id, c) => {
		const trial = c.code;
		if (!trial) return;
		const source = Object.values(trial.reference)
			.map((f) => f.toString())
			.join("\n");

		test("the reference passes its own suite, directly", () => {
			const g = runSuite(trial, (fn, ...args) =>
				(trial.reference[fn] as (...a: unknown[]) => unknown)(...args),
			);
			expect(g.results.filter((r) => r.error)).toEqual([]);
		});

		test("the same suite passes the reference's source inside the sandbox", () => {
			const g = grade(qjs, trial, source);
			expect(g.compileError).toBeNull();
			expect(g.results.filter((r) => r.error)).toEqual([]);
			expect(g.passed).toBe(true);
			g.code?.dispose();
		});

		test("the starter code compiles but does not pass yet", () => {
			const g = grade(qjs, trial, trial.starter);
			expect(g.compileError).toBeNull();
			expect(g.passed).toBe(false);
		});

		test("missing functions and syntax errors are reported, not thrown", () => {
			expect(grade(qjs, trial, "const x = 1;").compileError).toContain(
				"define function",
			);
			expect(grade(qjs, trial, "function (").compileError).toContain(
				"SyntaxError",
			);
		});
	},
);

describe("the sandbox", () => {
	test("has no network, storage, or host objects", () => {
		const code = new PlayerCode(
			qjs,
			"function probe() { return [typeof fetch, typeof XMLHttpRequest, typeof localStorage, typeof document, typeof process, typeof require, typeof Bun]; }",
			["probe"],
		);
		expect(code.call("probe")).toEqual(Array(7).fill("undefined"));
		code.dispose();
	});

	test("stops endless loops and runaway memory, and keeps working after", () => {
		const code = new PlayerCode(
			qjs,
			"function spin() { for (;;) {} } function hog() { const a = []; for (;;) a.push([1, 2, 3, 4]); } function ok(x) { return x + 1; }",
			["spin", "hog", "ok"],
		);
		expect(() => code.call("spin")).toThrow(/took longer than/);
		expect(() => code.call("hog")).toThrow(/out of memory/);
		expect(code.call("ok", 1)).toBe(2);
		code.dispose();
	});

	test("player code sees copies: it can't reach the game's objects", () => {
		const code = new PlayerCode(
			qjs,
			"function mutate(a) { a.push(99); return a.length; }",
			["mutate"],
		);
		const arr = [1, 2];
		expect(code.call("mutate", arr)).toBe(3);
		expect(arr).toEqual([1, 2]);
		code.dispose();
	});
});
