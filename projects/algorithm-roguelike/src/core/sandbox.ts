// Code mode: the player's JavaScript runs inside QuickJS compiled to WebAssembly, a separate engine with
// its own heap. It has no fetch, storage, DOM, or timers, a memory limit, and a time limit per call, and
// it only sees the plain data the game passes in (copied in and out as JSON).
import {
	newQuickJSWASMModuleFromVariant,
	type QuickJSContext,
	type QuickJSRuntime,
	type QuickJSWASMModule,
} from "quickjs-emscripten-core";
import type { CodeTrial } from "./types";

export const MEMORY_BYTES = 16 * 1024 * 1024;
export const CALL_MS = 250;

let engine: Promise<QuickJSWASMModule> | null = null;
/** Load QuickJS once (its own file, about 1 MB, fetched only now); everything after this is synchronous. */
export const loadSandbox = () => {
	engine ??= import("@jitl/quickjs-singlefile-mjs-release-sync").then((m) =>
		newQuickJSWASMModuleFromVariant(m.default),
	);
	return engine;
};

export class PlayerCode {
	private runtime: QuickJSRuntime;
	private ctx: QuickJSContext;
	private deadline = 0;
	readonly error: string | null;

	constructor(qjs: QuickJSWASMModule, source: string, exports: string[]) {
		this.runtime = qjs.newRuntime();
		this.runtime.setMemoryLimit(MEMORY_BYTES);
		this.runtime.setMaxStackSize(512 * 1024);
		this.runtime.setInterruptHandler(() => Date.now() > this.deadline);
		this.ctx = this.runtime.newContext();
		this.error = this.eval(
			`${source}\n;[${exports.map((e) => `typeof ${e}`).join(",")}].join(",")`,
			(kinds) => {
				const missing = exports.filter(
					(_, i) => String(kinds).split(",")[i] !== "function",
				);
				return missing.length
					? `define ${missing.map((m) => `function ${m}`).join(" and ")}`
					: null;
			},
		);
	}

	private eval(
		code: string,
		then: (value: unknown) => string | null,
	): string | null {
		this.deadline = Date.now() + CALL_MS * 4;
		const r = this.ctx.evalCode(code, "player.js");
		if (r.error) {
			const e = this.ctx.dump(r.error) as { name?: string; message?: string };
			r.error.dispose();
			return `${e.name ?? "Error"}: ${e.message ?? String(e)}`;
		}
		const v = this.ctx.dump(r.value);
		r.value.dispose();
		return then(v);
	}

	/** Call one of the player's functions with JSON-able arguments; throws on errors and time-outs. */
	call(name: string, ...args: unknown[]): unknown {
		this.deadline = Date.now() + CALL_MS;
		const r = this.ctx.evalCode(
			`JSON.stringify(${name}(...${JSON.stringify(args)}))`,
			"call.js",
		);
		if (r.error) {
			const e = this.ctx.dump(r.error) as { name?: string; message?: string };
			r.error.dispose();
			throw new Error(
				e.message === "interrupted"
					? `took longer than ${CALL_MS} ms`
					: `${e.name ?? "Error"}: ${e.message ?? String(e)}`,
			);
		}
		const text = this.ctx.dump(r.value);
		r.value.dispose();
		return typeof text === "string" ? JSON.parse(text) : undefined;
	}

	dispose() {
		this.ctx.dispose();
		this.runtime.dispose();
	}
}

export interface Grade {
	passed: boolean;
	results: { name: string; error: string | null }[];
	ms: number;
	compileError: string | null;
}

/** Run a trial's suite against a function caller (the player's sandboxed code, or the reference). */
export function runSuite(
	trial: CodeTrial,
	call: (fn: string, ...args: unknown[]) => unknown,
): Omit<Grade, "compileError"> {
	const t0 = performance.now();
	const results = trial.suite.map((c) => {
		try {
			return { name: c.name, error: c.run(call) };
		} catch (e) {
			return {
				name: c.name,
				error: e instanceof Error ? e.message : String(e),
			};
		}
	});
	const ms = performance.now() - t0;
	const slow = ms > trial.budgetMs;
	if (slow)
		results.push({
			name: `whole suite within ${trial.budgetMs} ms`,
			error: `took ${Math.round(ms)} ms`,
		});
	return { passed: results.every((r) => !r.error), results, ms };
}

/** Grade player source against a trial in the sandbox. Returns the loaded code too when it passes. */
export function grade(
	qjs: QuickJSWASMModule,
	trial: CodeTrial,
	source: string,
): Grade & { code: PlayerCode | null } {
	const code = new PlayerCode(qjs, source, trial.exports);
	if (code.error) {
		code.dispose();
		return {
			passed: false,
			results: [],
			ms: 0,
			compileError: code.error,
			code: null,
		};
	}
	const g = runSuite(trial, (fn, ...args) => code.call(fn, ...args));
	if (!g.passed) code.dispose();
	return { ...g, compileError: null, code: g.passed ? code : null };
}
