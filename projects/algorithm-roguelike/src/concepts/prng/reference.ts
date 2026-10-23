// Seeded pseudo-random numbers. A generator is a function from a state to the next state and a number;
// the same seed always gives the same numbers. `lcg` is the classic small one to work by hand; the game
// itself uses mulberry32 (src/core/rng.ts), which mixes its bits better.
export { mulberry32 } from "../../core/rng";

/** A linear congruential generator: next = (a × state + c) mod m. */
export const lcg = (a: number, c: number, m: number) => (state: number) =>
	(a * state + c) % m;

/** The first `n` numbers from a generator and a seed. */
export function sequence(
	next: (s: number) => number,
	seed: number,
	n: number,
): number[] {
	const out: number[] = [];
	let s = seed;
	for (let i = 0; i < n; i++) {
		s = next(s);
		out.push(s);
	}
	return out;
}
