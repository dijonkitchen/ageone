import { expect, test } from "bun:test";
import { fighter, SPECIAL_COST } from "./fighters";
import {
	DOWN,
	FPS,
	INTRO_FRAMES,
	type Input,
	KICK,
	LEFT,
	type Match,
	newMatch,
	PUNCH,
	RIGHT,
	ROUND_OVER_FRAMES,
	ROUND_SECONDS,
	SPECIAL,
	step,
	UP,
} from "./sim";

const kame = fighter("kame");

/** A match past its intro with the fighters `gap` pixels apart. */
function ready(gap = 30): Match {
	const m = newMatch(kame, kame);
	for (let i = 0; i < INTRO_FRAMES; i++) step(m, [0, 0]);
	expect(m.phase).toBe("fight");
	m.fighters[0].x = 160 - gap / 2;
	m.fighters[1].x = 160 + gap / 2;
	return m;
}

function run(m: Match, frames: number, p1: Input = 0, p2: Input = 0): Match {
	for (let i = 0; i < frames; i++) step(m, [p1, p2]);
	return m;
}

/** Press a button for one frame, then hold `after` for `frames`. */
function press(
	m: Match,
	p1: Input,
	p2: Input,
	frames: number,
	hold1 = 0,
	hold2 = 0,
): Match {
	step(m, [p1, p2]);
	return run(m, frames, hold1, hold2);
}

test("a punch in range hits, costs health, and builds meter", () => {
	const m = press(ready(), PUNCH, 0, 20);
	const [a, d] = m.fighters;
	expect(d.health).toBe(kame.health - kame.moves.punch.damage);
	expect(a.meter).toBe(kame.moves.punch.damage);
	expect(d.meter).toBeGreaterThan(0);
});

test("a punch out of range whiffs", () => {
	const m = press(ready(100), PUNCH, 0, 20);
	expect(m.fighters[1].health).toBe(kame.health);
});

test("holding away blocks a mid attack, standing or crouching", () => {
	for (const hold of [RIGHT, RIGHT | DOWN]) {
		const m = ready();
		press(m, PUNCH, hold, 20, 0, hold);
		expect(m.fighters[1].health).toBe(kame.health);
	}
});

test("lows must be blocked crouching, jump-ins standing", () => {
	const low = ready();
	press(low, DOWN | KICK, RIGHT, 30, DOWN, RIGHT);
	expect(low.fighters[1].health).toBeLessThan(kame.health);
	const lowBlocked = ready();
	press(lowBlocked, DOWN | KICK, RIGHT | DOWN, 30, DOWN, RIGHT | DOWN);
	expect(lowBlocked.fighters[1].health).toBe(kame.health);

	// Jump in from a distance and kick on the way down.
	const jumpIn = (guard: Input) => {
		const m = ready(90);
		run(m, 1, UP | RIGHT, guard);
		const a = m.fighters[0];
		while (a.vy > 0 || a.y > 45) run(m, 1, 0, guard);
		press(m, KICK, guard, 40, 0, guard);
		return m.fighters[1].health;
	};
	expect(jumpIn(RIGHT)).toBe(kame.health);
	expect(jumpIn(RIGHT | DOWN)).toBeLessThan(kame.health);
});

test("the special needs meter, fires one projectile, and chips through a block", () => {
	const m = ready(200);
	press(m, SPECIAL, 0, 5);
	expect(m.projectiles).toHaveLength(0); // no meter yet
	m.fighters[0].meter = SPECIAL_COST * 2;
	press(m, SPECIAL, 0, kame.moves.special.startup + 1);
	expect(m.projectiles).toHaveLength(1);
	expect(m.fighters[0].meter).toBe(SPECIAL_COST);
	press(m, SPECIAL, 0, 5);
	expect(m.projectiles).toHaveLength(1); // one at a time
	run(m, 120, 0, RIGHT);
	expect(m.projectiles).toHaveLength(0);
	expect(m.fighters[1].health).toBe(kame.health - kame.projectile.chip);
});

test("a knockout ends the round and two rounds win the match", () => {
	const m = ready();
	m.fighters[1].health = 1;
	press(m, PUNCH, 0, 1);
	run(m, 10);
	expect(m.phase).toBe("roundOver");
	expect(m.roundWinner).toBe(0);
	expect(m.wins).toEqual([1, 0]);
	run(m, ROUND_OVER_FRAMES);
	expect(m.round).toBe(2);
	expect(m.fighters[1].health).toBe(kame.health);
	run(m, INTRO_FRAMES);
	m.fighters[1].health = 1;
	m.fighters[0].x = 145;
	m.fighters[1].x = 175;
	press(m, PUNCH, 0, ROUND_OVER_FRAMES + 10);
	expect(m.phase).toBe("matchOver");
	expect(m.result).toBe(0);
});

test("at time up the healthier fighter wins the round", () => {
	const m = ready(200);
	m.fighters[0].health -= 10;
	run(m, ROUND_SECONDS * FPS);
	expect(m.phase).toBe("roundOver");
	expect(m.roundWinner).toBe(1);
});

test("walls hold, fighters can't overlap, and they turn to face each other", () => {
	const m = ready(100);
	run(m, 400, LEFT, LEFT);
	expect(m.fighters[0].x).toBe(12);
	expect(m.fighters[1].x - m.fighters[0].x).toBeGreaterThanOrEqual(21.99);
	run(m, 400, RIGHT, LEFT);
	expect(m.fighters[1].x - m.fighters[0].x).toBeGreaterThanOrEqual(21.99);
	expect(m.fighters.map((f) => f.facing)).toEqual([1, -1]);
});

test("the same inputs give the same match", () => {
	const script = (i: number): [Input, Input] => [
		[RIGHT, PUNCH, 0, KICK, UP | RIGHT, DOWN | KICK][i % 6] ?? 0,
		[LEFT, 0, KICK, PUNCH, LEFT | DOWN][(i * 7) % 5] ?? 0,
	];
	const play = () => {
		const m = newMatch(kame, fighter("rumble"));
		for (let i = 0; i < 3000; i++) step(m, script(Math.floor(i / 3)));
		return JSON.stringify(m);
	};
	expect(play()).toBe(play());
});
