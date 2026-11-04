import { expect, test } from "bun:test";
import { baselineAccuracy, type Labeled, modelAccuracy } from "./accuracy.ts";
import labeled from "./fixtures/labeled.json";

const set = labeled as Labeled[];

test("the labeled set has every sentiment and the word list misses a fair share", () => {
	expect(new Set(set.map((l) => l.label)).size).toBe(3);
	expect(baselineAccuracy(set)).toBeLessThan(0.7);
});

test("a perfect model scores 1; a fake that copies the word list does not beat it", async () => {
	const oracle = async (
		messages: readonly { role: string; content: string }[],
	) => {
		const data = JSON.parse(messages.at(-1)?.content ?? "{}") as {
			comments: { id: string }[];
		};
		return JSON.stringify({
			results: data.comments.map((c) => ({
				id: c.id,
				sentiment: set.find((l) => l.id === c.id)?.label,
				themes: [],
			})),
		});
	};
	expect(await modelAccuracy(oracle, set)).toBe(1);
});
