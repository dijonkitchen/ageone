// Headless CPU-versus-CPU matches: `bun harness.ts [matches] [level1] [level2]`, e.g. `bun harness.ts 50 hard easy`.
// Fighters rotate through the roster so every pairing is played.

import type { Level } from "./src/cpu";
import { FIGHTERS } from "./src/fighters";
import { simulate } from "./src/headless";

const [n = "50", l1 = "hard", l2 = "easy"] = process.argv.slice(2);
let won = 0;
let drawn = 0;
let frames = 0;
let hits = 0;
let blocks = 0;
const started = performance.now();
for (let i = 0; i < Number(n); i++) {
	const a = FIGHTERS[i % FIGHTERS.length];
	const b = FIGHTERS[(i * 3 + 1) % FIGHTERS.length];
	if (!a || !b) continue;
	const o = simulate(
		{ fighter: a, level: l1 as Level },
		{ fighter: b, level: l2 as Level },
		i,
	);
	if (o.result === 0) won++;
	if (o.result === "draw") drawn++;
	frames += o.frames;
	hits += o.hits;
	blocks += o.blocks;
}
const ms = performance.now() - started;
console.log(
	`${l1} vs ${l2}: ${won}/${n} won, ${drawn} drawn; ${frames} frames (${Math.round(frames / 60)} s of play) in ${Math.round(ms)} ms; ${hits} hits, ${blocks} blocks`,
);
