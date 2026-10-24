// The CPU player. It presses the same buttons a person would, through the same `Input` bitmask, and sees the
// opponent only as they were `reaction` frames ago. Levels change how fast it reacts and how often it blocks,
// never damage or speed.

import type { MoveId } from "./fighters";
import { SPECIAL_COST } from "./fighters";
import { type Rng, rng } from "./rng";
import {
	type Action,
	DOWN,
	type Input,
	KICK,
	LEFT,
	type Match,
	PUNCH,
	RIGHT,
	type Side,
	SPECIAL,
	UP,
} from "./sim";

export type Level = "easy" | "normal" | "hard";
export const LEVELS: readonly Level[] = ["easy", "normal", "hard"];

export interface Profile {
	reaction: number; // frames between something happening and the CPU seeing it
	block: number; // chance to block an attack it sees coming
	guard: number; // chance to hold back when the opponent is close and idle
	antiAir: number; // chance to punch a jump-in instead of blocking it
	aggression: number; // chance to attack when in range
	special: number; // chance to throw a special from far away
	think: number; // frames a plan lasts before the next decision
}

export const PROFILES: Record<Level, Profile> = {
	easy: {
		reaction: 24,
		block: 0.1,
		guard: 0.05,
		antiAir: 0.05,
		aggression: 0.35,
		special: 0.2,
		think: 16,
	},
	normal: {
		reaction: 14,
		block: 0.5,
		guard: 0.25,
		antiAir: 0.35,
		aggression: 0.5,
		special: 0.4,
		think: 10,
	},
	hard: {
		reaction: 6,
		block: 0.9,
		guard: 0.5,
		antiAir: 0.75,
		aggression: 0.6,
		special: 0.6,
		think: 6,
	},
};

/** What the CPU remembers of the opponent each frame. */
interface Seen {
	x: number;
	y: number;
	action: Action;
	move: MoveId | null;
	t: number;
	shot: number | null; // x of the opponent's projectile, if any
	shotVx: number;
}

export class Cpu {
	readonly profile: Profile;
	private readonly random: Rng;
	private readonly seen: Seen[] = [];
	private plan: Input = 0;
	private press: Input = 0; // buttons to press on the plan's first frame
	private left = 0;
	private threat: string | null = null; // the attack it last decided about
	private guarding = false;
	private last: Input = 0;

	constructor(level: Level, seed: number) {
		this.profile = PROFILES[level];
		this.random = rng(seed);
	}

	private view(m: Match, me: Side): Seen {
		const o = m.fighters[me === 0 ? 1 : 0];
		const shot = m.projectiles.find((p) => p.owner !== me);
		this.seen.push({
			x: o.x,
			y: o.y,
			action: o.action,
			move: o.move,
			t: o.t,
			shot: shot ? shot.x : null,
			shotVx: shot ? shot.vx : 0,
		});
		if (this.seen.length > this.profile.reaction + 1) this.seen.shift();
		return this.seen[0] as Seen;
	}

	/** The buttons held this frame by the CPU playing side `me`. */
	input(m: Match, me: Side): Input {
		const seen = this.view(m, me);
		const self = m.fighters[me];
		if (m.phase !== "fight") return this.hold(0);
		const towards = seen.x > self.x ? RIGHT : LEFT;
		const away = towards === RIGHT ? LEFT : RIGHT;
		const dist = Math.abs(seen.x - self.x);

		// Defence: an attack or projectile it can see coming.
		const danger = this.danger(seen, self.x, dist, m, me);
		if (danger) {
			if (this.threat !== danger.key) {
				this.threat = danger.key;
				this.guarding = this.random() < this.profile.block;
				if (danger.air && this.random() < this.profile.antiAir) {
					this.left = 0;
					this.guarding = false;
					return this.hold(0, PUNCH);
				}
			}
			if (this.guarding) {
				this.left = 0;
				return this.hold(away | (danger.low ? DOWN : 0));
			}
		} else this.threat = null;

		if (self.action === "air" && dist < 45 && seen.y < self.y + 20)
			return this.hold(this.plan, KICK);
		if (this.left > 0) {
			this.left--;
			return this.hold(this.plan);
		}
		this.decide(self.meter, dist, seen, towards, away);
		const press = this.press;
		this.press = 0;
		return this.hold(this.plan, press);
	}

	private danger(
		seen: Seen,
		x: number,
		dist: number,
		m: Match,
		me: Side,
	): { key: string; low: boolean; air: boolean } | null {
		if (seen.shot !== null) {
			const toward = (x - seen.shot) * seen.shotVx > 0;
			if (toward && Math.abs(x - seen.shot) < 90)
				return { key: "shot", low: false, air: false };
		}
		const o = m.fighters[me === 0 ? 1 : 0];
		if (seen.action === "attack" && seen.move && seen.move !== "special") {
			const move = o.def.moves[seen.move];
			if (dist < move.reach + 30 && seen.t < move.startup + move.active)
				return {
					key: `${seen.move}@${m.frame - seen.t - this.seen.length}`,
					low: move.height === "low",
					air: false,
				};
		}
		if ((seen.action === "air" || seen.action === "attack") && seen.y > 10)
			if (dist < 60) return { key: "air", low: false, air: true };
		return null;
	}

	private decide(
		meter: number,
		dist: number,
		seen: Seen,
		towards: Input,
		away: Input,
	): void {
		const p = this.profile;
		const r = this.random;
		this.left = p.think;
		this.plan = 0;
		this.press = 0;
		const busy = seen.action === "hitstun" || seen.action === "ko";
		if (meter >= SPECIAL_COST && dist > 110 && r() < p.special) {
			this.press = SPECIAL;
		} else if (dist < 38) {
			if (busy || r() < p.aggression) {
				const pick = r();
				if (pick < 0.45) this.press = PUNCH;
				else if (pick < 0.7) this.press = KICK;
				else {
					this.plan = DOWN;
					this.press = KICK;
				}
			} else if (r() < p.guard) this.plan = away;
		} else if (dist < 48 && r() < p.aggression) {
			this.press = KICK;
		} else if (r() < 0.12 * p.aggression && dist < 140) {
			this.plan = UP | towards;
			this.left = 4;
		} else this.plan = towards;
	}

	/** Hold `buttons`, plus `press` only if it was up last frame (so presses register). */
	private hold(buttons: Input, press: Input = 0): Input {
		const out = buttons | (press & ~this.last);
		this.last = out;
		return out;
	}
}
