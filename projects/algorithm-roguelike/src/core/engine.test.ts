import { beforeAll, describe, expect, test } from "bun:test";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { QuickJSWASMModule } from "quickjs-emscripten-core";
import { CONCEPTS } from "../concepts";
import {
	type Env,
	fingerprint,
	isSafe,
	learn,
	newRun,
	replay,
	step,
} from "./engine";
import { SHRINE, STAIRS } from "./grid";
import { Rng } from "./rng";
import { loadSandbox, PlayerCode } from "./sandbox";
import type { State } from "./types";

const env: Env = { concepts: CONCEPTS };
const TIER1 = CONCEPTS.filter((c) => c.tier === 1).map((c) => c.id);
const ALL = CONCEPTS.map((c) => c.id);

let qjs: QuickJSWASMModule;
beforeAll(async () => {
	qjs = await loadSandbox();
});

/** Random but legal-looking inputs, from a seed. */
function inputs(seed: number, n: number): string[] {
	const rng = new Rng(seed);
	const moves = [
		"move:1,0",
		"move:-1,0",
		"move:0,1",
		"move:0,-1",
		"move:1,1",
		"move:-1,-1",
		"move:1,-1",
		"move:-1,1",
	];
	return Array.from({ length: n }, () => {
		const r = rng.float();
		if (r < 0.75) return rng.pick(moves);
		if (r < 0.8) return "wait";
		if (r < 0.84) return "descend";
		if (r < 0.88) return `use:${rng.range(1, 3)}`;
		if (r < 0.92) return "act:throw";
		if (r < 0.95) return "act:quaff";
		return "act:undo";
	});
}

const rooms = (s: State) => new Set(s.floor.room.filter((r) => r >= 0)).size;

describe("floors grow with what you learn", () => {
	test("a new player starts in a single hand-made room with a shrine, stairs, and the first codex page", () => {
		const s = newRun(env, 1);
		expect(rooms(s)).toBe(1);
		expect(s.floor.tiles.filter((t) => t === SHRINE).length).toBe(1);
		expect(s.floor.tiles.filter((t) => t === STAIRS).length).toBe(1);
		expect(s.items.find((i) => i.kind === "page")?.concept).toBe("grid");
		expect(s.monsters.length).toBe(1);
	});

	test("with tier 1 learned, floors are rooms joined by corridors", () => {
		const s = newRun(env, 2, TIER1);
		expect(rooms(s)).toBe(6);
	});

	test("with tier 2 learned, floors are caves with fog of war and speed-based turns", () => {
		const s = newRun(env, 3, ALL);
		expect(rooms(s)).toBe(0);
		expect(s.floor.tiles.filter((t) => t !== "#").length).toBeGreaterThan(200);
		const before = s.time;
		step(env, s, "wait");
		expect(s.sched).not.toBeNull();
		expect(s.time).toBeGreaterThan(before);
		// Fog of war: seen cells are remembered after they leave view.
		expect(s.floor.seen.filter(Boolean).length).toBeGreaterThanOrEqual(
			s.visible.length,
		);
	});

	test("stairs lead down to a new floor built from what is learned now", () => {
		const s = newRun(env, 6);
		const i = s.floor.tiles.indexOf(STAIRS);
		s.player.x = i % s.floor.w;
		s.player.y = Math.trunc(i / s.floor.w);
		s.unlocked.push("grid");
		step(env, s, "descend");
		expect(s.depth).toBe(2);
		expect(rooms(s)).toBe(6);
	});

	test("each floor offers the next concept whose prerequisites are learned", () => {
		const s = newRun(env, 4, ["grid"]);
		const page = s.items.find((i) => i.kind === "page");
		expect(
			["stack", "bfs", "hashmap", "prng"].includes(page?.concept ?? ""),
		).toBe(true);
	});
});

describe("runs", () => {
	test("replay: the same seed and inputs give the same run", () => {
		for (const learned of [[], TIER1, ALL]) {
			for (const seed of [11, 12]) {
				const log = inputs(seed, 400);
				const a = replay(env, seed, learned, log);
				const b = replay(env, seed, learned, log);
				expect(fingerprint(a)).toBe(fingerprint(b));
			}
		}
	});

	test("different seeds give different runs", () => {
		expect(fingerprint(newRun(env, 1, ALL))).not.toBe(
			fingerprint(newRun(env, 2, ALL)),
		);
	});

	test("monsters never step into the shrine's safe area", () => {
		for (const learned of [TIER1, ALL]) {
			const s = newRun(env, 21, learned);
			for (const i of inputs(5, 300)) {
				step(env, s, i);
				for (const m of s.monsters)
					expect(isSafe(s.floor, m.x, m.y)).toBe(false);
				if (s.over) break;
			}
		}
	});

	test("learning needs the page, a shrine, and the prerequisites, and is an input so replays include it", () => {
		const s = newRun(env, 1);
		expect(learn(env, s, "grid")).toBe(false); // no page yet
		const page = s.items.find((i) => i.kind === "page");
		if (!page) throw new Error("no page");
		// Walk to the page, then back to the shrine, in a straight line (the first room is open).
		const walk = (tx: number, ty: number) => {
			while (s.player.x !== tx || s.player.y !== ty)
				step(
					env,
					s,
					`move:${Math.sign(tx - s.player.x)},${Math.sign(ty - s.player.y)}`,
				);
		};
		walk(page.x, page.y);
		expect(s.pages).toEqual(["grid"]);
		expect(learn(env, s, "grid")).toBe(false); // not on a shrine
		const i = s.floor.tiles.indexOf(SHRINE);
		walk(i % s.floor.w, Math.trunc(i / s.floor.w));
		step(env, s, "learn:stack");
		expect(s.unlocked).toEqual([]);
		step(env, s, "learn:grid");
		expect(s.unlocked).toEqual(["grid"]);
		expect(s.pages).toEqual([]);
	});

	test("undo (the stack) works once per floor", () => {
		const s = newRun(env, 8, ["grid", "stack"]);
		const start = [s.player.x, s.player.y];
		const moved = ["move:1,0", "move:-1,0", "move:0,1", "move:0,-1"].find(
			(m) => {
				step(env, s, m);
				return s.player.x !== start[0] || s.player.y !== start[1];
			},
		);
		expect(moved).toBeDefined();
		step(env, s, "act:undo");
		expect([s.player.x, s.player.y]).toEqual(start);
		step(env, s, moved as string);
		step(env, s, "act:undo");
		expect([s.player.x, s.player.y]).not.toEqual(start);
		expect(s.log.at(-1)).toContain("already");
	});

	test("the hash map stacks items by name; without it the pack holds 4 single items", () => {
		const plain = newRun(env, 1);
		const hashed = newRun(env, 1, ["grid", "hashmap"]);
		for (const s of [plain, hashed])
			for (let k = 0; k < 6; k++) {
				s.items.push({ x: s.player.x + 1, y: s.player.y, kind: "dart" });
				step(env, s, "move:1,0");
				step(env, s, "move:-1,0");
			}
		expect(plain.inventory.length).toBe(4);
		expect(hashed.inventory).toEqual([{ kind: "dart", count: 6 }]);
	});
});

describe("code mode in the game", () => {
	test("the player's BFS reveals rooms, and a crashing one falls back to the reference without ending the run", () => {
		const reference = CONCEPTS.find((c) => c.id === "bfs")?.code?.reference.bfs;
		if (!reference) throw new Error("no bfs reference");
		const bfsSource = reference.toString();
		let calls = 0;
		const good = new PlayerCode(qjs, bfsSource, ["bfs"]);
		const failures: string[] = [];
		const playerEnv: Env = {
			concepts: CONCEPTS,
			code: (name) =>
				name === "bfs"
					? (...args) => {
							calls++;
							return good.call("bfs", ...args);
						}
					: null,
			codeFailed: (name, why) => failures.push(`${name}: ${why}`),
		};
		const a = newRun(playerEnv, 30, TIER1);
		const b = newRun(env, 30, TIER1);
		expect(calls).toBeGreaterThan(0);
		expect(a.visible).toEqual(b.visible);
		good.dispose();

		const bad = new PlayerCode(qjs, "function bfs() { for (;;) {} }", ["bfs"]);
		const badEnv: Env = {
			...playerEnv,
			code: (name) =>
				name === "bfs" ? (...args) => bad.call("bfs", ...args) : null,
		};
		const c = newRun(badEnv, 30, TIER1);
		expect(c.visible).toEqual(b.visible);
		expect(failures[0]).toContain("took longer");
		expect(c.over).toBe(false);
		bad.dispose();
	});
});

test("the engine core never names a concept, so adding one needs no engine change", () => {
	const dir = join(import.meta.dir);
	for (const file of readdirSync(dir).filter(
		(f) => f.endsWith(".ts") && !f.endsWith(".test.ts"),
	)) {
		const text = readFileSync(join(dir, file), "utf8");
		expect(text, file).not.toMatch(/from "\.\.\/concepts/);
		for (const c of CONCEPTS)
			expect(text.includes(`"${c.id}"`), `${file} names ${c.id}`).toBe(false);
	}
});
