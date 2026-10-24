import { Rng } from "../../core/rng";
import type { Concept, Frame, ItemKind, PuzzleStep } from "../../core/types";
import { choice } from "../util";
import { buildAlias, sampleAlias } from "./reference";

/** Loot by rarity: common, rare, and epic, with epic items a little likelier deeper down. */
export const lootTable = (depth: number): [ItemKind, number][] => [
	["healing potion", 40],
	["dart", 30],
	["haste potion", 15],
	["vigor amulet", 4 + depth],
];

const NAMES = ["potion", "dart", "gem", "scroll"];

function columns(names: string[], prob: number[], alias: number[]): string[] {
	return prob.map(
		(p, i) =>
			`column ${i}: ${names[i]} ${(p * 100).toFixed(0)}%${p < 1 ? `, else ${names[alias[i] as number]}` : ""}`,
	);
}

function weightsFor(rng: Rng): number[] {
	for (;;) {
		const w = [
			rng.range(1, 6),
			rng.range(1, 6),
			rng.range(1, 6),
			rng.range(1, 6),
		];
		const sum = w.reduce((a, b) => a + b, 0);
		if (sum % 4 === 0 && new Set(w).size > 2) return w;
	}
}

function frames(seed: number): Frame[] {
	const rng = new Rng(seed);
	const w = weightsFor(rng);
	const total = w.reduce((a, b) => a + b, 0);
	const t = buildAlias(w);
	const out: Frame[] = [
		{
			caption: `Weights ${w.join(", ")}: scale each by 4 / ${total} so the average column is exactly full (1).`,
			lines: w.map(
				(x, i) =>
					`${NAMES[i]}: ${((x * 4) / total).toFixed(2)} ${"█".repeat(Math.round((x * 16) / total))}`,
			),
			data: [],
		},
		{
			caption:
				"Pair each short column with a tall one: the tall one tops up the short one to 1 and shrinks by the same amount.",
			lines: columns(NAMES, t.prob, t.alias),
			data: [
				`prob = [${t.prob.map((p) => p.toFixed(2)).join(", ")}]`,
				`alias = [${t.alias.join(", ")}]`,
			],
		},
	];
	for (let k = 0; k < 3; k++) {
		const u1 = rng.float();
		const u2 = rng.float();
		const r = sampleAlias(t, u1, u2);
		out.push({
			caption: `Draw: column ${Math.floor(u1 * 4)} (from ${u1.toFixed(2)}), coin ${u2.toFixed(2)} → ${NAMES[r]}.`,
			lines: columns(NAMES, t.prob, t.alias),
			data: ["one column, one coin flip: O(1) per draw"],
		});
	}
	return out;
}

export const concept: Concept = {
	id: "alias",
	name: "Weighted random (alias method)",
	tier: 2,
	requires: ["prng"],
	unlocks:
		"loot tables with rarity tiers: rare haste potions and epic vigor amulets.",
	complexity: { time: "O(n) to build, O(1) per draw", space: "O(n)" },
	reading: {
		title: "Darts, Dice, and Coins (Keith Schwarz)",
		url: "https://www.keithschwarz.com/darts-dice-coins/",
	},
	lesson: {
		text: [
			"Loot tables are weighted: a healing potion should drop far more often than an amulet. The simple way rolls a number up to the total weight and walks down the list, which takes longer the longer the list.",
			"The alias method does the work once, up front. Scale the weights so the average is 1, then picture each outcome as a column. Short columns (under 1) get topped up from a tall one, which shrinks by the same amount, until every column is exactly full.",
			"Each column now holds at most two outcomes: its own, with some probability, and its alias. To draw, pick a column at random and flip a coin weighted by that probability.",
			"Setup is O(n); every draw after that is O(1), however many items the table holds.",
		],
		frames,
	},
	puzzle(seed) {
		const rng = new Rng(seed);
		const w = weightsFor(rng);
		const total = w.reduce((a, b) => a + b, 0);
		const t = buildAlias(w);
		const scaled = w.map((x) => (x * 4) / total);
		const steps: PuzzleStep[] = [];
		const i = rng.int(4);
		steps.push(
			choice(
				rng,
				`Weights ${NAMES.map((n, k) => `${n} ${w[k]}`).join(", ")} (total ${total}). Scaled so the average is 1, how tall is the ${NAMES[i]} column?`,
				(scaled[i] as number).toFixed(2),
				[
					((w[i] as number) / total).toFixed(2),
					(w[i] as number).toFixed(2),
					((scaled[i] as number) + 0.5).toFixed(2),
				],
				`${w[i]} × 4 / ${total} = ${(scaled[i] as number).toFixed(2)}.`,
			),
		);
		const firstSmall = scaled.findIndex((v) => v < 1);
		const firstLarge = scaled.findIndex((v) => v >= 1);
		if (firstSmall >= 0 && firstLarge >= 0)
			steps.push(
				choice(
					rng,
					`Scaled: ${NAMES.map((n, k) => `${n} ${(scaled[k] as number).toFixed(2)}`).join(", ")}. Pairing the first short column with the first tall one, what is the ${NAMES[firstSmall]} column's alias?`,
					NAMES[firstLarge] as string,
					NAMES.filter((_, k) => k !== firstSmall),
					`${NAMES[firstSmall]} is the first column under 1 and ${NAMES[firstLarge]} the first at 1 or more: it tops ${NAMES[firstSmall]} up, so it is the alias.`,
				),
			);
		for (let k = 0; k < 4; k++) {
			const col = rng.int(4);
			const u2 = Math.round(rng.float() * 100) / 100;
			const r = sampleAlias(t, (col + 0.5) / 4, u2);
			steps.push(
				choice(
					rng,
					`The table: ${columns(NAMES, t.prob, t.alias).join("; ")}. You pick column ${col} and the coin comes up ${u2.toFixed(2)}. Which item drops?`,
					NAMES[r] as string,
					NAMES,
					`Keep column ${col}'s own item if the coin is under ${((t.prob[col] as number) * 100).toFixed(0)}%, otherwise take its alias: ${NAMES[r]}.`,
				),
			);
		}
		return {
			intro: "Build an alias table and draw from it by hand.",
			steps,
			slack: 2,
		};
	},
	hooks: {
		loot: {
			priority: 1,
			roll(ctx, depth) {
				const table = lootTable(depth);
				const t = buildAlias(table.map(([, w]) => w));
				return (
					table[sampleAlias(t, ctx.rng.float(), ctx.rng.float())] as [
						ItemKind,
						number,
					]
				)[0];
			},
		},
	},
};
