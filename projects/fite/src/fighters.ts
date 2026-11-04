// The roster: four turtle ninjas and the boss, with per-fighter frame data built from one base move set.
// All names and designs are original to this game.

export type MoveId =
	| "punch"
	| "kick"
	| "lowPunch"
	| "lowKick"
	| "airKick"
	| "special";

/** Where an attack lands: lows must be blocked crouching, highs (jump-ins) standing, mids either way. */
export type Height = "low" | "mid" | "high";

export interface Move {
	startup: number; // frames before the hitbox appears
	active: number; // frames the hitbox is out
	recovery: number; // frames after, before the fighter can act
	damage: number;
	hitstun: number;
	blockstun: number;
	reach: number; // hitbox length in front of the body, in pixels
	bottom: number; // hitbox bottom, in pixels above the fighter's feet
	top: number; // hitbox top, likewise
	push: number; // knockback speed on hit, in pixels per frame
	height: Height;
}

export interface ProjectileDef {
	speed: number;
	damage: number;
	chip: number; // damage through a block
	hitstun: number;
	blockstun: number;
	radius: number;
	color: Rgb;
}

export type Rgb = readonly [number, number, number];

export interface FighterDef {
	id: string;
	name: string;
	style: string; // one line for the select screen
	bandana: Rgb;
	shell: Rgb;
	skin: Rgb;
	walk: number; // pixels per frame
	jump: number; // takeoff speed, pixels per frame
	health: number;
	moves: Record<MoveId, Move>;
	projectile: ProjectileDef;
	boss: boolean;
}

/** The meter a special costs, out of METER_MAX. */
export const SPECIAL_COST = 50;
export const METER_MAX = 100;

const BASE: Record<MoveId, Move> = {
	punch: {
		startup: 4,
		active: 3,
		recovery: 8,
		damage: 5,
		hitstun: 14,
		blockstun: 9,
		reach: 22,
		bottom: 30,
		top: 42,
		push: 2.5,
		height: "mid",
	},
	kick: {
		startup: 7,
		active: 4,
		recovery: 13,
		damage: 8,
		hitstun: 18,
		blockstun: 12,
		reach: 30,
		bottom: 14,
		top: 28,
		push: 3.5,
		height: "mid",
	},
	lowPunch: {
		startup: 4,
		active: 3,
		recovery: 9,
		damage: 4,
		hitstun: 13,
		blockstun: 8,
		reach: 20,
		bottom: 10,
		top: 22,
		push: 2,
		height: "low",
	},
	lowKick: {
		startup: 8,
		active: 4,
		recovery: 15,
		damage: 7,
		hitstun: 18,
		blockstun: 12,
		reach: 32,
		bottom: 0,
		top: 8,
		push: 3,
		height: "low",
	},
	airKick: {
		startup: 5,
		active: 8,
		recovery: 4,
		damage: 8,
		hitstun: 18,
		blockstun: 11,
		reach: 22,
		bottom: 4,
		top: 24,
		push: 3,
		height: "high",
	},
	special: {
		startup: 12,
		active: 1,
		recovery: 18,
		damage: 0, // the projectile does the damage
		hitstun: 0,
		blockstun: 0,
		reach: 0,
		bottom: 0,
		top: 0,
		push: 0,
		height: "mid",
	},
};

interface Tuning {
	power: number; // damage multiplier
	reach: number; // reach multiplier
	speed: number; // startup frames added (negative is faster), never below 2
}

function moveSet(t: Tuning): Record<MoveId, Move> {
	const out = {} as Record<MoveId, Move>;
	for (const [id, m] of Object.entries(BASE) as [MoveId, Move][])
		out[id] = {
			...m,
			startup: Math.max(2, m.startup + (id === "special" ? 0 : t.speed)),
			damage: Math.round(m.damage * t.power),
			reach: Math.round(m.reach * t.reach),
		};
	return out;
}

const SKIN: Rgb = [110, 178, 74];

export const FIGHTERS: readonly FighterDef[] = [
	{
		id: "kame",
		name: "KAME",
		style: "BALANCED",
		bandana: [32, 168, 168],
		shell: [140, 96, 52],
		skin: SKIN,
		walk: 1.5,
		jump: 6.4,
		health: 100,
		moves: moveSet({ power: 1, reach: 1, speed: 0 }),
		projectile: {
			speed: 3,
			damage: 10,
			chip: 2,
			hitstun: 20,
			blockstun: 14,
			radius: 5,
			color: [120, 220, 255],
		},
		boss: false,
	},
	{
		id: "zip",
		name: "ZIP",
		style: "FAST",
		bandana: [232, 184, 40],
		shell: [128, 104, 60],
		skin: [124, 186, 80],
		walk: 1.9,
		jump: 6.8,
		health: 95,
		moves: moveSet({ power: 0.85, reach: 0.95, speed: -1 }),
		projectile: {
			speed: 4,
			damage: 8,
			chip: 2,
			hitstun: 18,
			blockstun: 12,
			radius: 4,
			color: [255, 240, 120],
		},
		boss: false,
	},
	{
		id: "rumble",
		name: "RUMBLE",
		style: "STRONG",
		bandana: [208, 64, 160],
		shell: [112, 80, 48],
		skin: [96, 160, 70],
		walk: 1.15,
		jump: 6.0,
		health: 110,
		moves: moveSet({ power: 1.2, reach: 1, speed: 1 }),
		projectile: {
			speed: 2.5,
			damage: 13,
			chip: 3,
			hitstun: 22,
			blockstun: 16,
			radius: 6,
			color: [255, 140, 220],
		},
		boss: false,
	},
	{
		id: "reed",
		name: "REED",
		style: "LONG REACH",
		bandana: [120, 132, 156],
		shell: [150, 112, 70],
		skin: [118, 172, 96],
		walk: 1.4,
		jump: 6.4,
		health: 100,
		moves: moveSet({ power: 0.95, reach: 1.2, speed: 0 }),
		projectile: {
			speed: 3.5,
			damage: 9,
			chip: 2,
			hitstun: 19,
			blockstun: 13,
			radius: 4,
			color: [200, 220, 240],
		},
		boss: false,
	},
	{
		id: "snapjaw",
		name: "SNAPJAW",
		style: "THE BOSS",
		bandana: [40, 40, 48],
		shell: [64, 72, 56],
		skin: [86, 120, 60],
		walk: 1.4,
		jump: 6.2,
		health: 140,
		moves: moveSet({ power: 1.15, reach: 1.1, speed: 0 }),
		projectile: {
			speed: 3.5,
			damage: 12,
			chip: 3,
			hitstun: 22,
			blockstun: 16,
			radius: 6,
			color: [255, 96, 64],
		},
		boss: true,
	},
];

export const PLAYABLE = FIGHTERS.filter((f) => !f.boss);
export const BOSS = FIGHTERS.find((f) => f.boss) as FighterDef;

export function fighter(id: string): FighterDef {
	const def = FIGHTERS.find((f) => f.id === id);
	if (!def) throw new Error(`no fighter ${id}`);
	return def;
}

export const totalFrames = (m: Move): number =>
	m.startup + m.active + m.recovery;
