// Runs matches with no browser: two CPU players, the real simulation, and checks that the state stays sane.
// The harness script (harness.ts) and the tests use it; CI runs thousands of frames through it.

import { Cpu, type Level } from "./cpu";
import type { FighterDef } from "./fighters";
import {
	FPS,
	MAX_ROUNDS,
	type Match,
	newMatch,
	ROUND_SECONDS,
	type Side,
	step,
	WALL,
	WIDTH,
} from "./sim";

export interface Player {
	fighter: FighterDef;
	level: Level;
}

export interface Outcome {
	result: Side | "draw";
	wins: [number, number];
	rounds: number;
	frames: number;
	hits: number;
	blocks: number;
}

// Every round can last its full clock plus the intro and round-over pauses.
const FRAME_LIMIT = MAX_ROUNDS * (ROUND_SECONDS * FPS + 300);

/** Throws if the match is in a state the rules don't allow. */
export function checkInvariants(m: Match): void {
	for (const f of m.fighters) {
		for (const v of [f.x, f.y, f.vx, f.vy, f.health, f.meter])
			if (!Number.isFinite(v))
				throw new Error(`non-finite value in ${f.def.id}`);
		if (f.x < WALL - 0.001 || f.x > WIDTH - WALL + 0.001)
			throw new Error(`${f.def.id} left the stage at x=${f.x}`);
		if (f.y < 0) throw new Error(`${f.def.id} fell through the floor`);
		if (f.health < 0 || f.health > f.def.health)
			throw new Error(`${f.def.id} health ${f.health} out of range`);
		if (f.meter < 0 || f.meter > 100)
			throw new Error(`${f.def.id} meter ${f.meter} out of range`);
	}
	if (m.projectiles.filter((p) => p.owner === 0).length > 1)
		throw new Error("two projectiles from one player");
	if (m.clock < 0) throw new Error("negative clock");
}

export function simulate(p1: Player, p2: Player, seed: number): Outcome {
	const m = newMatch(p1.fighter, p2.fighter);
	const cpus = [
		new Cpu(p1.level, seed * 2 + 1),
		new Cpu(p2.level, seed * 2 + 2),
	];
	let hits = 0;
	let blocks = 0;
	while (m.phase !== "matchOver") {
		if (m.frame > FRAME_LIMIT) throw new Error("match never ended");
		step(m, [cpus[0]?.input(m, 0) ?? 0, cpus[1]?.input(m, 1) ?? 0]);
		checkInvariants(m);
		for (const e of m.events) {
			if (e.type === "hit") hits++;
			if (e.type === "block") blocks++;
		}
	}
	return {
		result: m.result ?? "draw",
		wins: m.wins,
		rounds: m.round,
		frames: m.frame,
		hits,
		blocks,
	};
}
