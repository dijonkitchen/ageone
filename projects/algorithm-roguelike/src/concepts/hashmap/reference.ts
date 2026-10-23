// A hash table with separate chaining: a key's hash picks a bucket, and each bucket is a short list of
// [key, value] pairs. With enough buckets, a lookup checks only a few pairs, whatever the table's size.

/** A small teaching hash: the sum of the letters' positions in the alphabet (a = 1), modulo the buckets. */
export function letterHash(key: string, buckets: number): number {
	let sum = 0;
	for (const ch of key.toLowerCase())
		if (ch >= "a" && ch <= "z") sum += ch.charCodeAt(0) - 96;
	return sum % buckets;
}

export class HashTable<V> {
	buckets: [string, V][][];
	constructor(
		size = 8,
		private readonly hash: (
			key: string,
			buckets: number,
		) => number = letterHash,
	) {
		this.buckets = Array.from({ length: size }, () => []);
	}
	private bucket(key: string): [string, V][] {
		return this.buckets[this.hash(key, this.buckets.length)] as [string, V][];
	}
	set(key: string, value: V) {
		const b = this.bucket(key);
		const pair = b.find(([k]) => k === key);
		if (pair) pair[1] = value;
		else b.push([key, value]);
	}
	get(key: string): V | undefined {
		return this.bucket(key).find(([k]) => k === key)?.[1];
	}
	delete(key: string): boolean {
		const b = this.bucket(key);
		const i = b.findIndex(([k]) => k === key);
		if (i < 0) return false;
		b.splice(i, 1);
		return true;
	}
	get size() {
		return this.buckets.reduce((n, b) => n + b.length, 0);
	}
}
