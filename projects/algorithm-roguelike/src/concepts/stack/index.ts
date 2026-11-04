import { restore, say } from "../../core/engine";
import { Rng } from "../../core/rng";
import type { Concept, Frame, PuzzleStep } from "../../core/types";
import { choice } from "../util";
import { Stack } from "./reference";

const WORDS = [
	"move east",
	"move north",
	"drink potion",
	"move west",
	"pick up dart",
	"move south",
	"attack rat",
	"wait",
];

const show = (items: string[]) =>
	items.length
		? items
				.map((v, i) => `${i === items.length - 1 ? "top → " : "      "}${v}`)
				.reverse()
		: ["(empty)"];

function frames(seed: number): Frame[] {
	const rng = new Rng(seed);
	const s = new Stack<string>();
	const out: Frame[] = [
		{ caption: "An empty stack.", lines: show([]), data: ["size 0"] },
	];
	for (let k = 0; k < 4; k++) {
		const w = rng.pick(WORDS);
		s.push(w);
		out.push({
			caption: `You ${w}: push it on top.`,
			lines: show(s.toArray()),
			data: [`push("${w}")`, `size ${s.size}`],
		});
	}
	for (let k = 0; k < 2; k++) {
		const w = s.pop();
		out.push({
			caption: `Undo: pop the top, "${w}", the last thing done.`,
			lines: show(s.toArray()),
			data: [`pop() → "${w}"`, `size ${s.size}`],
		});
	}
	return out;
}

export const concept: Concept = {
	id: "stack",
	name: "Stack",
	tier: 1,
	requires: ["grid"],
	unlocks: "undo your last move once per floor (z).",
	complexity: { time: "O(1) push and pop", space: "O(n)" },
	reading: {
		title: "Stack (Wikipedia)",
		url: "https://en.wikipedia.org/wiki/Stack_(abstract_data_type)",
	},
	lesson: {
		text: [
			"A stack is a pile: you put things on top (push) and take them off the top (pop). The last thing in is the first thing out.",
			"Undo is a stack. Before each move the game pushes a copy of the world; undo pops the latest copy and puts it back.",
			"Both operations touch only the end of an array, so they take the same short time however tall the stack grows.",
			"Stacks also let you backtrack: walking into a dead end, you pop your way back to the last fork. Depth-first search, later, works exactly like that.",
		],
		frames,
	},
	puzzle(seed) {
		const rng = new Rng(seed);
		const s = new Stack<string>();
		const steps: PuzzleStep[] = [];
		const log: string[] = [];
		let next = 0;
		const letters = "ABCDEFGHIJ";
		while (steps.length < 6) {
			if (s.size === 0 || (s.size < 4 && rng.chance(0.55))) {
				const v = letters[next++ % letters.length] as string;
				s.push(v);
				log.push(`push ${v}`);
				continue;
			}
			const before = s.toArray();
			const v = s.pop() as string;
			steps.push(
				choice(
					rng,
					`After: ${log.join(", ")}. What does pop return?`,
					v,
					[...before, ...letters.slice(0, Math.max(next, 4))],
					`The top is the last one pushed and not yet popped: ${v}. The stack was [${before.join(", ")}] (top at the right).`,
				),
			);
			log.push(`pop → ${v}`);
		}
		return {
			intro: "Play the stack: say what each pop takes off the top.",
			steps,
			slack: 1,
		};
	},
	hooks: {
		actions: {
			undo: {
				key: "z",
				label: "Undo your last move (once per floor)",
				run(_ctx, s) {
					if (s.undo.used) say(s, "You already undid a move on this floor.");
					else {
						const saved = s.undo.stack.pop();
						if (!saved) say(s, "There is nothing to undo yet.");
						else {
							restore(s, saved);
							s.undo.used = true;
							say(s, "You pop the last move off the stack: undone.");
						}
					}
					return false;
				},
			},
		},
	},
};
