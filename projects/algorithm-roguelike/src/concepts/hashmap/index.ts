import { say, useItem } from "../../core/engine";
import { Rng } from "../../core/rng";
import type { Concept, Frame, PuzzleStep } from "../../core/types";
import { choice } from "../util";
import { HashTable, letterHash } from "./reference";

const KEYS = [
	"dart",
	"potion",
	"rat",
	"bat",
	"amulet",
	"goblin",
	"zombie",
	"torch",
	"rope",
	"key",
	"map",
	"gem",
];
const SIZE = 7;

const show = (t: HashTable<number>) =>
	t.buckets.map(
		(b, i) => `${i}: ${b.map(([k, v]) => `${k}=${v}`).join(" → ") || "·"}`,
	);

function frames(seed: number): Frame[] {
	const rng = new Rng(seed);
	const t = new HashTable<number>(SIZE);
	const out: Frame[] = [
		{
			caption: `${SIZE} empty buckets.`,
			lines: show(t),
			data: ["hash(key) = sum of letter positions (a = 1) mod 7"],
		},
	];
	for (const k of rng.shuffle([...KEYS]).slice(0, 6)) {
		const h = letterHash(k, SIZE);
		t.set(k, (t.get(k) ?? 0) + 1);
		out.push({
			caption: `"${k}" hashes to bucket ${h}; add it there (a bucket can hold several keys).`,
			lines: show(t),
			data: [`hash("${k}") = ${h}`, `size ${t.size}`],
		});
	}
	const k = rng.pick([...t.buckets.flat().map(([key]) => key)]);
	out.push({
		caption: `Looking up "${k}" checks only bucket ${letterHash(k, SIZE)}, not the whole table.`,
		lines: show(t),
		data: [`get("${k}") = ${t.get(k)}`],
	});
	return out;
}

export const concept: Concept = {
	id: "hashmap",
	name: "Hash map",
	tier: 1,
	requires: ["grid"],
	unlocks:
		"your pack stacks items by name and holds 10 kinds; q drinks a healing potion, found by name.",
	complexity: { time: "O(1) on average to set or get", space: "O(n)" },
	reading: {
		title: "Hash table (Wikipedia)",
		url: "https://en.wikipedia.org/wiki/Hash_table",
	},
	lesson: {
		text: [
			"A hash map stores values by key, such as item counts by item name, and finds a key without searching through all the others.",
			"It keeps an array of buckets. A hash function turns the key into a number, and that number modulo the number of buckets says which bucket the key lives in.",
			"Two keys can land in the same bucket (a collision). Each bucket holds a short list, so the map checks just that list.",
			"With a good hash and enough buckets, the lists stay short, and setting or getting a key takes about the same time however many keys there are.",
			"Here the hash is simply the sum of the letters' positions in the alphabet, so you can work it out by hand.",
		],
		frames,
	},
	puzzle(seed) {
		const rng = new Rng(seed);
		const t = new HashTable<number>(SIZE);
		const steps: PuzzleStep[] = [];
		const keys = rng.shuffle([...KEYS]).slice(0, 5);
		for (const k of keys) {
			const h = letterHash(k, SIZE);
			const sum = Array.from(k).reduce((n, ch) => n + ch.charCodeAt(0) - 96, 0);
			steps.push(
				choice(
					rng,
					`With ${SIZE} buckets and hash = sum of letter positions (a = 1) mod ${SIZE}, which bucket does "${k}" go in?`,
					String(h),
					Array.from({ length: SIZE }, (_, i) => String(i)),
					`${Array.from(k)
						.map((ch) => ch.charCodeAt(0) - 96)
						.join(" + ")} = ${sum}, and ${sum} mod ${SIZE} = ${h}.`,
					show(t),
				),
			);
			t.set(k, 1);
		}
		const k = rng.pick(keys);
		const bucket = t.buckets[letterHash(k, SIZE)] as [string, number][];
		steps.push(
			choice(
				rng,
				`Looking up "${k}" now, how many keys does the map compare it with?`,
				String(bucket.findIndex(([x]) => x === k) + 1),
				["1", "2", "3", String(t.size)],
				`Only bucket ${letterHash(k, SIZE)} is searched, in order, until "${k}" is found.`,
				show(t),
			),
		);
		return { intro: "Hash keys into buckets by hand.", steps, slack: 1 };
	},
	hooks: {
		inventory: { priority: 1, stacks: true, limit: 10 },
		actions: {
			quaff: {
				key: "q",
				label: "Drink a healing potion (looked up by name)",
				run(_ctx, s) {
					const byName = new HashTable<number>(16);
					s.inventory.forEach((st, i) => {
						byName.set(st.kind, i);
					});
					const slot = byName.get("healing potion");
					if (slot === undefined) {
						say(s, "You have no healing potion.");
						return false;
					}
					return useItem(s, slot);
				},
			},
		},
	},
};
