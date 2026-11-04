import { expect, test } from "bun:test";
import { ask } from "./ask";
import { FakeAnswer, FakeSearch } from "./providers";
import {
	INDEX_PATH,
	loadIndex,
	rebuildIndex,
	search,
	serializeIndex,
	tokenize,
} from "./search";
import { MemoryVault } from "./vault";

async function filled() {
	const vault = new MemoryVault();
	let t = 0;
	for (const q of [
		"tardigrade survival",
		"rust ownership",
		"tardigrade genome",
	])
		await ask(q, {
			vault,
			search: new FakeSearch(),
			model: new FakeAnswer(),
			now: () => new Date(Date.UTC(2026, 9, 23, 12, 0, t++)),
		});
	return vault;
}

test("tokenize lowercases and splits on punctuation", () => {
	expect(tokenize("Rust's Ownership—2x!")).toEqual([
		"rust",
		"s",
		"ownership",
		"2x",
	]);
});

test("search finds notes containing every term", async () => {
	const vault = await filled();
	const index = await loadIndex(vault);
	expect(search(index, "tardigrade")).toHaveLength(2);
	expect(search(index, "tardigrade genome")).toHaveLength(1);
	expect(search(index, "nonexistent")).toEqual([]);
	expect(search(index, "")).toEqual([]);
});

test("rebuilding a deleted index from the vault gives identical results", async () => {
	const vault = await filled();
	const before = (await vault.read(INDEX_PATH)) ?? "";
	await vault.remove(INDEX_PATH);
	const rebuilt = await rebuildIndex(vault);
	expect(serializeIndex(rebuilt)).toBe(before);
	expect(await vault.read(INDEX_PATH)).toBe(before);
	expect(search(rebuilt, "tardigrade")).toEqual(
		search(JSON.parse(before), "tardigrade"),
	);
});

test("a damaged index is rebuilt", async () => {
	const vault = await filled();
	await vault.write(INDEX_PATH, "{nope");
	expect(search(await loadIndex(vault), "rust")).toHaveLength(1);
});
