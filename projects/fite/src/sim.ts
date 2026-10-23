// The fight itself: a deterministic fixed-step simulation of two fighters, their projectiles, and a best-of-three
// match. No randomness, no DOM, no clock: `step` advances one frame (1/60 s) from the two players' inputs, so the
// browser, the headless harness, and the tests all run the same code.

import {
	type FighterDef,
	METER_MAX,
	type Move,
	type MoveId,
	type ProjectileDef,
	SPECIAL_COST,
	totalFrames,
} from "./fighters";

// Inputs are bitmasks of held buttons; the simulation finds presses itself.
export const UP = 1;
export const DOWN = 2;
export const LEFT = 4;
export const RIGHT = 8;
export const PUNCH = 16;
export const KICK = 32;
export const SPECIAL = 64;
export const START = 128;
export type Input = number;

export const WIDTH = 320;
export const HEIGHT = 180;
export const GROUND = 160; // screen y of the floor
export const FPS = 60;
export const ROUND_SECONDS = 60;
export const ROUNDS_TO_WIN = 2;
export const MAX_ROUNDS = 5; // drawn rounds count for no one; after this many the match is a draw
export const INTRO_FRAMES = 90;
export const ROUND_OVER_FRAMES = 150;
export const WALL = 12;
export const BODY_HALF = 11;
export const GRAVITY = 0.35;
export const JUMP_SPEED_X = 2.2;
const BACK_WALK = 0.8; // walking backward is slower

export type Action =
	| "stand"
	| "crouch"
	| "air"
	| "attack"
	| "hitstun"
	| "blockstun"
	| "ko"
	| "victory";

export interface Fighter {
	def: FighterDef;
	x: number;
	y: number; // height above the floor; 0 is standing on it
	vx: number;
	vy: number; // upward is positive
	facing: 1 | -1;
	health: number;
	meter: number;
	action: Action;
	move: MoveId | null;
	t: number; // frames in the current action
	stun: number; // frames of hitstun or blockstun left
	connected: boolean; // the current attack already hit or was blocked
	airAttacked: boolean; // one air attack per jump
	walking: -1 | 0 | 1; // relative to facing: 1 forward, -1 back
	input: Input;
	prev: Input;
}

export interface Projectile {
	owner: 0 | 1;
	x: number;
	y: number;
	vx: number;
	def: ProjectileDef;
	t: number;
}

export type EventType = "hit" | "block" | "whoosh" | "special" | "ko" | "round";
export interface SimEvent {
	type: EventType;
	x: number;
	y: number;
}

export type Phase = "intro" | "fight" | "roundOver" | "matchOver";
export type Side = 0 | 1;

export interface Match {
	fighters: [Fighter, Fighter];
	projectiles: Projectile[];
	phase: Phase;
	t: number; // frames in the current phase
	frame: number;
	round: number;
	clock: number; // frames left in the round
	wins: [number, number];
	roundWinner: Side | "draw" | null;
	result: Side | "draw" | null;
	events: SimEvent[]; // what happened this frame, for sound and effects
}

function newFighter(def: FighterDef, side: Side): Fighter {
	return {
		def,
		x: side === 0 ? WIDTH / 2 - 60 : WIDTH / 2 + 60,
		y: 0,
		vx: 0,
		vy: 0,
		facing: side === 0 ? 1 : -1,
		health: def.health,
		meter: 0,
		action: "stand",
		move: null,
		t: 0,
		stun: 0,
		connected: false,
		airAttacked: false,
		walking: 0,
		input: 0,
		prev: 0,
	};
}

export function newMatch(p1: FighterDef, p2: FighterDef): Match {
	return {
		fighters: [newFighter(p1, 0), newFighter(p2, 1)],
		projectiles: [],
		phase: "intro",
		t: 0,
		frame: 0,
		round: 1,
		clock: ROUND_SECONDS * FPS,
		wins: [0, 0],
		roundWinner: null,
		result: null,
		events: [],
	};
}

/** Seconds left on the round clock, as shown. */
export const seconds = (m: Match): number => Math.ceil(m.clock / FPS);

const backward = (f: Fighter): Input => (f.facing > 0 ? LEFT : RIGHT);
const grounded = (f: Fighter): boolean => f.y <= 0;

/** The fighter's body box: [left, right, bottom, top], with y measured up from the floor. */
export function hurtbox(f: Fighter): [number, number, number, number] {
	const tall =
		f.action === "crouch" || isCrouching(f) ? 30 : grounded(f) ? 46 : 40;
	return [f.x - BODY_HALF, f.x + BODY_HALF, f.y, f.y + tall];
}

const isCrouching = (f: Fighter): boolean =>
	f.action === "crouch" ||
	(f.action === "attack" && (f.move === "lowPunch" || f.move === "lowKick")) ||
	(f.action === "blockstun" && (f.input & DOWN) !== 0 && grounded(f));

/** The attack's hitbox while it is active, else null. */
export function hitbox(f: Fighter): [number, number, number, number] | null {
	if (f.action !== "attack" || !f.move || f.move === "special") return null;
	const m = f.def.moves[f.move];
	if (f.connected || f.t < m.startup || f.t >= m.startup + m.active)
		return null;
	const near = f.x + f.facing * BODY_HALF;
	const far = near + f.facing * m.reach;
	return [
		Math.min(near, far),
		Math.max(near, far),
		f.y + m.bottom,
		f.y + m.top,
	];
}

const overlaps = (
	a: [number, number, number, number],
	b: [number, number, number, number],
): boolean => a[0] < b[1] && b[0] < a[1] && a[2] < b[3] && b[2] < a[3];

function startAttack(f: Fighter, move: MoveId, m: Match): void {
	f.action = "attack";
	f.move = move;
	f.t = 0;
	f.connected = false;
	if (grounded(f)) f.vx = 0;
	m.events.push({ type: "whoosh", x: f.x, y: f.y + 30 });
}

function act(f: Fighter, m: Match, side: Side): void {
	const input = f.input;
	const pressed = input & ~f.prev;
	const dir = (input & RIGHT ? 1 : 0) - (input & LEFT ? 1 : 0);
	const ownShot = m.projectiles.some((p) => p.owner === side);
	f.walking = 0;
	if (pressed & SPECIAL && f.meter >= SPECIAL_COST && !ownShot) {
		f.meter -= SPECIAL_COST;
		startAttack(f, "special", m);
	} else if (pressed & PUNCH)
		startAttack(f, input & DOWN ? "lowPunch" : "punch", m);
	else if (pressed & KICK) startAttack(f, input & DOWN ? "lowKick" : "kick", m);
	else if (input & UP) {
		f.action = "air";
		f.t = 0;
		f.vy = f.def.jump;
		f.vx = dir * JUMP_SPEED_X;
		f.airAttacked = false;
	} else if (input & DOWN) {
		if (f.action !== "crouch") f.t = 0;
		f.action = "crouch";
		f.vx = 0;
	} else {
		if (f.action !== "stand") f.t = 0;
		f.action = "stand";
		const back = dir !== 0 && dir !== f.facing;
		f.vx = dir * f.def.walk * (back ? BACK_WALK : 1);
		f.walking = dir === 0 ? 0 : back ? -1 : 1;
	}
}

function fall(f: Fighter): boolean {
	f.x += f.vx;
	f.y += f.vy;
	f.vy -= GRAVITY;
	if (f.y > 0) return false;
	f.y = 0;
	f.vy = 0;
	return true;
}

function update(f: Fighter, m: Match, side: Side): void {
	f.t++;
	switch (f.action) {
		case "stand":
		case "crouch":
			act(f, m, side);
			f.x += f.vx;
			break;
		case "air":
			if (!f.airAttacked && f.input & ~f.prev & (PUNCH | KICK)) {
				f.airAttacked = true;
				f.action = "attack";
				f.move = "airKick";
				f.t = 0;
				f.connected = false;
				m.events.push({ type: "whoosh", x: f.x, y: f.y + 20 });
			}
			if (fall(f)) {
				f.action = "stand";
				f.t = 0;
				f.vx = 0;
			}
			break;
		case "attack": {
			const move = f.def.moves[f.move as MoveId];
			if (f.move === "special" && f.t === move.startup) {
				const p = f.def.projectile;
				m.projectiles.push({
					owner: side,
					x: f.x + f.facing * (BODY_HALF + p.radius),
					y: 30,
					vx: f.facing * p.speed,
					def: p,
					t: 0,
				});
				m.events.push({ type: "special", x: f.x, y: 30 });
			}
			if (f.move === "airKick") {
				if (fall(f)) {
					f.action = "stand";
					f.move = null;
					f.t = 0;
					f.vx = 0;
				}
			} else if (f.t >= totalFrames(move)) {
				f.action = "stand";
				f.move = null;
				f.t = 0;
			}
			break;
		}
		case "hitstun":
		case "blockstun": {
			f.stun--;
			const landed = grounded(f) ? true : fall(f);
			if (landed) {
				f.x += f.vx;
				f.vx *= 0.8;
			}
			if (f.stun <= 0 && landed) {
				f.action = "stand";
				f.t = 0;
				f.vx = 0;
			}
			break;
		}
		case "ko":
			if (!fall(f)) break;
			f.vx *= 0.8;
			break;
		case "victory":
			break;
	}
	f.prev = f.input;
}

/** Whether the defender, as they stand now, blocks an attack of this height. */
function blocks(d: Fighter, height: Move["height"]): boolean {
	if (!grounded(d)) return false;
	if (!["stand", "crouch", "blockstun"].includes(d.action)) return false;
	if ((d.input & backward(d)) === 0) return false;
	const low = (d.input & DOWN) !== 0;
	return height === "mid" || (height === "low") === low;
}

interface Hit {
	from: Side;
	damage: number;
	chip: number;
	hitstun: number;
	blockstun: number;
	push: number;
	height: Move["height"];
	dir: 1 | -1; // direction of knockback
	x: number;
	y: number;
}

function land(m: Match, h: Hit): void {
	const a = m.fighters[h.from];
	const d = m.fighters[h.from === 0 ? 1 : 0];
	if (d.action === "ko") return;
	if (blocks(d, h.height)) {
		d.action = "blockstun";
		d.stun = h.blockstun;
		d.t = 0;
		d.vx = h.dir * h.push * 0.6;
		d.health = Math.max(1, d.health - h.chip);
		d.meter = Math.min(METER_MAX, d.meter + 3);
		a.meter = Math.min(METER_MAX, a.meter + 2);
		m.events.push({ type: "block", x: h.x, y: h.y });
		return;
	}
	d.health = Math.max(0, d.health - h.damage);
	d.action = "hitstun";
	d.stun = h.hitstun;
	d.t = 0;
	d.move = null;
	d.vx = h.dir * h.push;
	if (!grounded(d)) d.vy = 2;
	a.meter = Math.min(METER_MAX, a.meter + h.damage);
	d.meter = Math.min(METER_MAX, d.meter + Math.ceil(h.damage / 2));
	m.events.push({ type: "hit", x: h.x, y: h.y });
	if (d.health <= 0) {
		d.action = "ko";
		d.vy = 3;
		d.vx = h.dir * 2;
		m.events.push({ type: "ko", x: d.x, y: d.y + 30 });
	}
}

function collide(m: Match): void {
	const hits: Hit[] = [];
	for (const side of [0, 1] as const) {
		const a = m.fighters[side];
		const d = m.fighters[side === 0 ? 1 : 0];
		const box = hitbox(a);
		if (!box || !overlaps(box, hurtbox(d))) continue;
		const move = a.def.moves[a.move as MoveId];
		a.connected = true;
		hits.push({
			from: side,
			damage: move.damage,
			chip: 0,
			hitstun: move.hitstun,
			blockstun: move.blockstun,
			push: move.push,
			height: move.height,
			dir: a.facing,
			x:
				(Math.max(box[0], hurtbox(d)[0]) + Math.min(box[1], hurtbox(d)[1])) / 2,
			y: (box[2] + box[3]) / 2,
		});
	}
	// Projectiles cancel each other, then hit whoever they reach.
	const [p0, p1] = [0, 1].map((s) => m.projectiles.find((p) => p.owner === s));
	if (p0 && p1 && Math.abs(p0.x - p1.x) < p0.def.radius + p1.def.radius) {
		m.projectiles = [];
		m.events.push({ type: "block", x: (p0.x + p1.x) / 2, y: p0.y });
	}
	m.projectiles = m.projectiles.filter((p) => {
		const d = m.fighters[p.owner === 0 ? 1 : 0];
		const r = p.def.radius;
		if (
			d.action !== "ko" &&
			overlaps([p.x - r, p.x + r, p.y - r, p.y + r], hurtbox(d))
		) {
			hits.push({
				from: p.owner,
				damage: p.def.damage,
				chip: p.def.chip,
				hitstun: p.def.hitstun,
				blockstun: p.def.blockstun,
				push: 2.5,
				height: "mid",
				dir: p.vx > 0 ? 1 : -1,
				x: p.x,
				y: p.y,
			});
			return false;
		}
		return p.x > -r && p.x < WIDTH + r;
	});
	// Trades: both hits land, computed from the same frame.
	for (const h of hits) land(m, h);
}

function separate(m: Match): void {
	const [a, b] = m.fighters;
	for (const f of m.fighters) f.x = Math.min(WIDTH - WALL, Math.max(WALL, f.x));
	const gap = Math.abs(a.x - b.x);
	const min = BODY_HALF * 2;
	if (gap >= min || Math.abs(a.y - b.y) > 36) return;
	const push = (min - gap) / 2;
	const dir = a.x < b.x || (a.x === b.x && a.facing > 0) ? -1 : 1;
	a.x += dir * push;
	b.x -= dir * push;
	// Against a wall, the other fighter takes the whole push.
	for (const [f, o] of [
		[a, b],
		[b, a],
	] as const) {
		if (f.x < WALL) {
			o.x += WALL - f.x;
			f.x = WALL;
		} else if (f.x > WIDTH - WALL) {
			o.x -= f.x - (WIDTH - WALL);
			f.x = WIDTH - WALL;
		}
	}
}

function face(m: Match): void {
	const [a, b] = m.fighters;
	for (const [f, o] of [
		[a, b],
		[b, a],
	] as const)
		if ((f.action === "stand" || f.action === "crouch") && o.x !== f.x)
			f.facing = o.x > f.x ? 1 : -1;
}

function resetRound(m: Match): void {
	const [a, b] = m.fighters;
	m.fighters = [newFighter(a.def, 0), newFighter(b.def, 1)];
	m.fighters[0].meter = a.meter;
	m.fighters[1].meter = b.meter;
	m.projectiles = [];
	m.round++;
	m.clock = ROUND_SECONDS * FPS;
	m.roundWinner = null;
	m.phase = "intro";
	m.t = 0;
}

function endRound(m: Match): void {
	const [a, b] = m.fighters;
	const ko = [a.health <= 0, b.health <= 0];
	let winner: Side | "draw";
	if (ko[0] && ko[1]) winner = "draw";
	else if (ko[0]) winner = 1;
	else if (ko[1]) winner = 0;
	else {
		const share = a.health / a.def.health - b.health / b.def.health;
		winner = share > 0 ? 0 : share < 0 ? 1 : "draw";
	}
	if (winner !== "draw") m.wins[winner]++;
	m.roundWinner = winner;
	m.phase = "roundOver";
	m.t = 0;
	m.events.push({ type: "round", x: WIDTH / 2, y: 90 });
}

function finishRound(m: Match): void {
	const [w0, w1] = m.wins;
	if (w0 >= ROUNDS_TO_WIN || w1 >= ROUNDS_TO_WIN || m.round >= MAX_ROUNDS) {
		m.result = w0 > w1 ? 0 : w1 > w0 ? 1 : "draw";
		m.phase = "matchOver";
		m.t = 0;
	} else resetRound(m);
}

/** Advance the match one frame. Mutates and returns it. */
export function step(m: Match, inputs: readonly [Input, Input]): Match {
	m.events = [];
	m.frame++;
	m.t++;
	const live = m.phase === "fight";
	m.fighters[0].input = live ? (inputs[0] ?? 0) : 0;
	m.fighters[1].input = live ? (inputs[1] ?? 0) : 0;
	if (m.phase === "intro" && m.t >= INTRO_FRAMES) {
		m.phase = "fight";
		m.t = 0;
	}
	if (m.phase === "matchOver") return m;
	update(m.fighters[0], m, 0);
	update(m.fighters[1], m, 1);
	for (const p of m.projectiles) {
		p.x += p.vx;
		p.t++;
	}
	collide(m);
	separate(m);
	face(m);
	if (m.phase === "fight") {
		m.clock--;
		if (m.fighters.some((f) => f.health <= 0) || m.clock <= 0) endRound(m);
	} else if (m.phase === "roundOver") {
		if (m.t === 60)
			for (const [i, f] of m.fighters.entries())
				if (m.roundWinner === i && grounded(f) && f.action !== "ko") {
					f.action = "victory";
					f.t = 0;
					f.vx = 0;
				}
		if (m.t >= ROUND_OVER_FRAMES) finishRound(m);
	}
	return m;
}
