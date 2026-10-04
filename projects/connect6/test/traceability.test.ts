import { describe, expect, it } from "bun:test";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import {
	type Agent,
	HeuristicAgent,
	LlmAgent,
	MctsAgent,
	RandomAgent,
} from "../src/core/index.js";

const root = join(import.meta.dir, "..");

/** Every ID a test name cites, expanding ranges like AC-WIN-1/2. */
const cited = (): Set<string> => {
	const ids = new Set<string>();
	for (const file of readdirSync(join(root, "test"))) {
		const text = readFileSync(join(root, "test", file), "utf8");
		for (const match of text.matchAll(/AC-([A-Z]+)-([\d/]+)/g)) {
			for (const n of (match[2] ?? "").split("/")) {
				if (n) ids.add(`AC-${match[1]}-${n}`);
			}
		}
	}
	return ids;
};

describe("traceability (specs/rules.md §6)", () => {
	it("every acceptance criterion is cited by a test", () => {
		const spec = readFileSync(join(root, "specs", "rules.md"), "utf8");
		const ids = [...spec.matchAll(/\*\*(AC-[A-Z]+-\d+)\*\*/g)].map((m) => m[1]);
		expect(ids.length).toBeGreaterThan(20);
		const tested = cited();
		expect(ids.filter((id) => id && !tested.has(id))).toEqual([]);
	});

	it("AC-PLAYERS-1: every player implements the one Agent interface", () => {
		const players: Agent[] = [
			new RandomAgent(),
			new HeuristicAgent(),
			new MctsAgent(),
			new LlmAgent(async () => ({ content: "", tokens: 0, cost: 0 })),
		];
		for (const player of players) {
			expect(typeof player.name).toBe("string");
			expect(typeof player.chooseMove).toBe("function");
		}
	});
});
