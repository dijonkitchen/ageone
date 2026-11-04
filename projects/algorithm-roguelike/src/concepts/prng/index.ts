import { mulberry32, Rng } from "../../core/rng";
import type { Concept, Frame, PuzzleStep } from "../../core/types";
import { choice } from "../util";
import { lcg, sequence } from "./reference";

function frames(seed: number): Frame[] {
	const rng = new Rng(seed);
	const s0 = rng.int(16);
	const next = lcg(5, 3, 16);
	const out: Frame[] = [];
	let s = s0;
	for (let i = 0; i < 6; i++) {
		const n = next(s);
		out.push({
			caption: `State ${s}: (5 × ${s} + 3) mod 16 = ${n}.`,
			lines: [`seed ${s0}: ${sequence(next, s0, i + 1).join(" ")}`],
			data: [`state = ${n}`],
		});
		s = n;
	}
	out.push({
		caption:
			"Start again from the same seed: the same numbers, in the same order. That is what makes a run replayable.",
		lines: [
			`seed ${s0}: ${sequence(next, s0, 6).join(" ")}`,
			`seed ${s0}: ${sequence(next, s0, 6).join(" ")}`,
		],
		data: [],
	});
	const g = (seedValue: number) => {
		let st = seedValue;
		return Array.from({ length: 4 }, () => {
			const [n, f] = mulberry32(st);
			st = n;
			return f.toFixed(3);
		}).join(" ");
	};
	out.push({
		caption:
			"The game's generator, mulberry32, works the same way with a 32-bit state and better mixing.",
		lines: [`seed 1: ${g(1)}`, `seed 2: ${g(2)}`, `seed 1: ${g(1)}`],
		data: [],
	});
	return out;
}

export const concept: Concept = {
	id: "prng",
	name: "Seeded PRNG",
	tier: 1,
	requires: ["grid"],
	unlocks:
		"seeded runs: see and type a seed, play the daily seed, and save or load replays.",
	complexity: {
		time: "O(1) per number",
		space: "O(1): the state is one number",
	},
	reading: {
		title: "Linear congruential generator (Wikipedia)",
		url: "https://en.wikipedia.org/wiki/Linear_congruential_generator",
	},
	lesson: {
		text: [
			"Computers can't roll dice. A pseudo-random number generator (PRNG) fakes it: a function turns a state into the next state, and each state gives a number that looks random.",
			"The first state is the seed. The same seed gives the same sequence every time, which is why a seeded run can be replayed or shared.",
			"The simplest kind is a linear congruential generator: next = (a × state + c) mod m. With a = 5, c = 3, and m = 16 you can follow it by hand.",
			"Small generators repeat soon and have patterns, so the game uses mulberry32, which mixes the bits of a 32-bit state. Every die roll, map, and monster move in a run comes from it.",
		],
		frames,
	},
	puzzle(seed) {
		const rng = new Rng(seed);
		const steps: PuzzleStep[] = [];
		const next = lcg(5, 3, 16);
		let s = rng.int(16);
		for (let i = 0; i < 4; i++) {
			const n = next(s);
			steps.push(
				choice(
					rng,
					`next = (5 × state + 3) mod 16. The state is ${s}. What comes next?`,
					String(n),
					[
						String((5 * s) % 16),
						String((5 * s + 3) % 15),
						String((s + 3) % 16),
						String(5 * s + 3),
						String((n + 1) % 16),
					],
					`5 × ${s} + 3 = ${5 * s + 3}, and ${5 * s + 3} mod 16 = ${n}.`,
				),
			);
			s = n;
		}
		const a = rng.int(16);
		const seq = sequence(next, a, 4).join(" ");
		steps.push(
			choice(
				rng,
				`Seed ${a} gave ${seq}. Started again from seed ${a}, what does it give?`,
				seq,
				[
					sequence(next, (a + 1) % 16, 4).join(" "),
					sequence(next, (a + 5) % 16, 4).join(" "),
					"something different each time",
				],
				"The generator is a fixed function of its state, so the same seed always gives the same sequence.",
			),
		);
		return { intro: "Step a seeded generator by hand.", steps, slack: 1 };
	},
	hooks: { features: ["seeds"] },
};
