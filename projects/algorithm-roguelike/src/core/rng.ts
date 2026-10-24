// The game's random numbers: mulberry32, a small seeded generator whose whole state is one 32-bit
// number, so a run is a pure function of its seed and inputs and the state saves as plain JSON.
// The seeded PRNG concept teaches this exact function.

/** Advance a mulberry32 state; returns the new state and a float in [0, 1). */
export function mulberry32(state: number): [number, number] {
	const next = (state + 0x6d2b79f5) | 0;
	let t = next;
	t = Math.imul(t ^ (t >>> 15), t | 1);
	t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
	return [next, ((t ^ (t >>> 14)) >>> 0) / 4294967296];
}

/** A generator over a state cell, so callers share one stream (the run's `rng` field). */
export class Rng {
	constructor(public state: number) {}
	float(): number {
		const [s, f] = mulberry32(this.state);
		this.state = s;
		return f;
	}
	/** An integer in [0, n). */
	int(n: number): number {
		return Math.floor(this.float() * n);
	}
	/** An integer in [lo, hi]. */
	range(lo: number, hi: number): number {
		return lo + this.int(hi - lo + 1);
	}
	chance(p: number): boolean {
		return this.float() < p;
	}
	pick<T>(items: readonly T[]): T {
		if (!items.length) throw new Error("pick from nothing");
		return items[this.int(items.length)] as T;
	}
	shuffle<T>(items: T[]): T[] {
		for (let i = items.length - 1; i > 0; i--) {
			const j = this.int(i + 1);
			[items[i], items[j]] = [items[j] as T, items[i] as T];
		}
		return items;
	}
}

/** A 32-bit seed from any text (a typed seed, or a date for the daily run). */
export function seedFrom(text: string): number {
	let h = 2166136261;
	for (let i = 0; i < text.length; i++)
		h = Math.imul(h ^ text.charCodeAt(i), 16777619);
	return h >>> 0;
}
