import { expect, test } from "bun:test";
import { HashTable, letterHash } from "./reference";

test("the letter hash sums alphabet positions", () => {
	expect(letterHash("dart", 7)).toBe((4 + 1 + 18 + 20) % 7);
	expect(letterHash("Rat!", 100)).toBe(18 + 1 + 20);
});

test("set, get, update, and delete, through collisions", () => {
	const t = new HashTable<number>(3);
	const keys = ["dart", "rat", "bat", "gem", "key", "map"];
	keys.forEach((k, i) => {
		t.set(k, i);
	});
	keys.forEach((k, i) => {
		expect(t.get(k)).toBe(i);
	});
	expect(t.buckets.some((b) => b.length > 1)).toBe(true);
	t.set("rat", 99);
	expect(t.get("rat")).toBe(99);
	expect(t.size).toBe(6);
	expect(t.delete("rat")).toBe(true);
	expect(t.delete("rat")).toBe(false);
	expect(t.get("rat")).toBeUndefined();
});
