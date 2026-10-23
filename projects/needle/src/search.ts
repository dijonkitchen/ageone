// Full-text search over the vault's notes. The index is a cache: it is rebuilt from the notes, never the source of truth.
import type { Vault } from "./vault";

export const INDEX_PATH = ".needle/index.json";

export type Index = Record<string, Record<string, number>>; // term -> path -> count

export function tokenize(text: string): string[] {
	return text.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? [];
}

export function buildIndex(docs: Map<string, string>): Index {
	const index: Index = {};
	for (const path of [...docs.keys()].sort()) {
		for (const term of tokenize(docs.get(path) ?? "")) {
			const postings = index[term] ?? {};
			index[term] = postings;
			postings[path] = (postings[path] ?? 0) + 1;
		}
	}
	return index;
}

export async function rebuildIndex(vault: Vault): Promise<Index> {
	const docs = new Map<string, string>();
	for (const path of await vault.list()) {
		if (!path.startsWith("research/") || !path.endsWith(".md")) continue;
		docs.set(path, (await vault.read(path)) ?? "");
	}
	const index = buildIndex(docs);
	await vault.write(INDEX_PATH, serializeIndex(index));
	return index;
}

// Sorted keys, so two builds of the same notes are byte-identical.
export function serializeIndex(index: Index): string {
	const sorted: Index = {};
	for (const term of Object.keys(index).sort()) {
		const postings = index[term] ?? {};
		const entry: Record<string, number> = {};
		for (const path of Object.keys(postings).sort())
			entry[path] = postings[path] ?? 0;
		sorted[term] = entry;
	}
	return JSON.stringify(sorted);
}

export async function loadIndex(vault: Vault): Promise<Index> {
	const saved = await vault.read(INDEX_PATH);
	if (saved) {
		try {
			return JSON.parse(saved) as Index;
		} catch {
			// A damaged cache is rebuilt below.
		}
	}
	return rebuildIndex(vault);
}

// Notes containing every query term, best match first, ties by path.
export function search(index: Index, query: string): string[] {
	const terms = [...new Set(tokenize(query))];
	if (!terms.length) return [];
	const scores = new Map<string, number>();
	terms.forEach((term, i) => {
		const postings = index[term] ?? {};
		if (i === 0)
			for (const [p, n] of Object.entries(postings)) scores.set(p, n);
		else
			for (const [p, s] of scores)
				postings[p] ? scores.set(p, s + (postings[p] ?? 0)) : scores.delete(p);
	});
	return [...scores.entries()]
		.sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
		.map(([p]) => p);
}
