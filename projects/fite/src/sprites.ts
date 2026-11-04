// Procedural pixel-art fighters from one shared rig: each pose is a handful of joint angles, and every fighter is
// the same rig drawn in its own colours (the boss adds ridges and a beak). `sheet()` draws every pose of every
// fighter into one image; the page cuts frames from it, and CI checks it matches the committed sprites/sheet.png.

import { FIGHTERS, type FighterDef, type Rgb } from "./fighters";
import {
	circle,
	ellipse,
	line,
	outline,
	type Pixels,
	pixels,
	rect,
	set,
	shade,
} from "./pixels";
import { DOWN, type Fighter, LEFT, RIGHT } from "./sim";

export const CELL = 64;
const ORIGIN_X = 26; // the fighter's x within a cell
export const FEET_Y = 62; // the floor's y within a cell
const THIGH = 8;
const SHIN = 8;
const UPPER_ARM = 7;
const FOREARM = 7;
const TORSO = 13;
const OUTLINE: Rgb = [24, 16, 32];
const PLASTRON: Rgb = [226, 204, 120];

type Limb = readonly [number, number]; // degrees: the joint's angle from straight down (forward is positive), then the bend

interface Pose {
	lean: number; // torso tilt forward, degrees
	hip?: number; // hip height for poses off the ground; standing poses put the lowest foot on the floor
	frontArm: Limb;
	backArm: Limb;
	frontLeg: Limb;
	backLeg: Limb;
	tails: number; // bandana tails, degrees from hanging straight down
	eyes?: "open" | "shut";
}

const STANCE = { frontLeg: [18, -14], backLeg: [-14, -4] } as const;
const GUARD = { frontArm: [35, 95], backArm: [20, 110] } as const;
const CROUCH = { frontLeg: [75, -115], backLeg: [40, -120] } as const;

export const POSES = {
	idle0: { lean: 8, ...GUARD, ...STANCE, tails: 50 },
	idle1: {
		lean: 10,
		frontArm: [38, 95],
		backArm: [22, 108],
		frontLeg: [22, -22],
		backLeg: [-16, -10],
		tails: 58,
	},
	walk0: {
		lean: 10,
		...GUARD,
		frontLeg: [28, -10],
		backLeg: [-22, -10],
		tails: 62,
	},
	walk1: {
		lean: 10,
		...GUARD,
		frontLeg: [8, -30],
		backLeg: [-8, -6],
		tails: 70,
	},
	walk2: {
		lean: 10,
		...GUARD,
		frontLeg: [-22, -10],
		backLeg: [28, -10],
		tails: 62,
	},
	walk3: {
		lean: 10,
		...GUARD,
		frontLeg: [-8, -6],
		backLeg: [8, -30],
		tails: 70,
	},
	crouch: {
		lean: 22,
		frontArm: [50, 90],
		backArm: [40, 100],
		...CROUCH,
		tails: 40,
	},
	jump: {
		lean: 10,
		hip: 24,
		frontArm: [60, 70],
		backArm: [30, 90],
		frontLeg: [70, -120],
		backLeg: [40, -110],
		tails: 15,
	},
	punch0: {
		lean: 4,
		frontArm: [-20, 120],
		backArm: [40, 90],
		...STANCE,
		tails: 55,
	},
	punch1: {
		lean: 16,
		frontArm: [90, 0],
		backArm: [10, 120],
		frontLeg: [24, -10],
		backLeg: [-24, 0],
		tails: 80,
	},
	kick0: {
		lean: -10,
		...GUARD,
		frontLeg: [70, -100],
		backLeg: [-4, -4],
		tails: 55,
	},
	kick1: {
		lean: -25,
		frontArm: [40, 80],
		backArm: [-30, 60],
		frontLeg: [92, -4],
		backLeg: [-6, -2],
		tails: 85,
	},
	lowPunch: {
		lean: 26,
		frontArm: [80, 8],
		backArm: [30, 110],
		...CROUCH,
		tails: 60,
	},
	lowKick: {
		lean: -6,
		frontArm: [40, 90],
		backArm: [-30, 40],
		frontLeg: [88, 0],
		backLeg: [45, -115],
		tails: 70,
	},
	airKick: {
		lean: -15,
		hip: 24,
		frontArm: [50, 90],
		backArm: [-40, 60],
		frontLeg: [55, 0],
		backLeg: [20, -100],
		tails: 20,
	},
	special0: {
		lean: -8,
		frontArm: [-40, 100],
		backArm: [-30, 100],
		...STANCE,
		tails: 45,
	},
	special1: {
		lean: 15,
		frontArm: [85, 5],
		backArm: [80, 10],
		frontLeg: [24, -10],
		backLeg: [-24, 0],
		tails: 85,
	},
	block: {
		lean: -4,
		frontArm: [70, 140],
		backArm: [60, 130],
		...STANCE,
		tails: 45,
	},
	crouchBlock: {
		lean: 14,
		frontArm: [70, 140],
		backArm: [60, 130],
		...CROUCH,
		tails: 35,
	},
	hit: {
		lean: -25,
		frontArm: [-30, 40],
		backArm: [-50, 30],
		frontLeg: [10, -20],
		backLeg: [-20, -5],
		tails: 30,
		eyes: "shut",
	},
	ko: {
		lean: -84,
		hip: 6,
		frontArm: [-150, 20],
		backArm: [-130, 10],
		frontLeg: [84, 0],
		backLeg: [80, -10],
		tails: 0,
		eyes: "shut",
	},
	victory: {
		lean: 0,
		frontArm: [175, 0],
		backArm: [20, 110],
		frontLeg: [14, -6],
		backLeg: [-14, -4],
		tails: 75,
	},
} satisfies Record<string, Pose>;

export type PoseName = keyof typeof POSES;
export const POSE_NAMES = Object.keys(POSES) as PoseName[];

const rad = (deg: number) => (deg * Math.PI) / 180;
const toward = (deg: number, length: number): [number, number] => [
	Math.sin(rad(deg)) * length,
	Math.cos(rad(deg)) * length,
];
const reachDown = ([a, b]: Limb) =>
	THIGH * Math.cos(rad(a)) + SHIN * Math.cos(rad(a + b));

/** Draw one fighter in one pose into `p`, with its feet at (x, y), facing right. */
export function drawFighter(
	p: Pixels,
	def: FighterDef,
	pose: Pose,
	x: number,
	y: number,
): void {
	const hipHeight =
		pose.hip ?? Math.max(reachDown(pose.frontLeg), reachDown(pose.backLeg));
	const hip: [number, number] = [x, y - hipHeight];
	const up: [number, number] = [
		Math.sin(rad(pose.lean)),
		-Math.cos(rad(pose.lean)),
	];
	const fwd: [number, number] = [
		Math.cos(rad(pose.lean)),
		Math.sin(rad(pose.lean)),
	];
	const along = (
		o: [number, number],
		t: number,
		n: number,
	): [number, number] => [
		o[0] + up[0] * t + fwd[0] * n,
		o[1] + up[1] * t + fwd[1] * n,
	];
	const shoulder = along(hip, TORSO, 0);
	const skin = def.skin;
	const back = shade(skin, -0.25);

	const limb = (
		from: [number, number],
		[a, b]: Limb,
		l1: number,
		l2: number,
		w: number,
		c: Rgb,
		end: number,
	) => {
		const [dx, dy] = toward(a, l1);
		const joint: [number, number] = [from[0] + dx, from[1] + dy];
		const [ex, ey] = toward(a + b, l2);
		line(p, from[0], from[1], joint[0], joint[1], w, c);
		line(p, joint[0], joint[1], joint[0] + ex, joint[1] + ey, w, c);
		circle(p, joint[0] + ex, joint[1] + ey, end, shade(c, -0.1));
	};

	limb(along(hip, 0, -1), pose.backLeg, THIGH, SHIN, 4, back, 2.2);
	limb(along(shoulder, -1, -1), pose.backArm, UPPER_ARM, FOREARM, 3, back, 2);

	// Shell on the back, plastron on the front, belt at the hip.
	const shellAt = along(hip, 7, -3);
	const angle = rad(pose.lean);
	ellipse(p, shellAt[0], shellAt[1], 7.5, 10, shade(def.shell, -0.35), angle);
	ellipse(p, shellAt[0], shellAt[1], 6.3, 8.8, def.shell, angle);
	const glint = along(hip, 10, -5);
	ellipse(p, glint[0], glint[1], 1.6, 3, shade(def.shell, 0.3), angle);
	for (const t of [4, 8, 12]) {
		const a = along(hip, t, -8.5);
		const b = along(hip, t, 0);
		line(p, a[0], a[1], b[0], b[1], 1, shade(def.shell, -0.35));
	}
	if (def.boss)
		for (const t of [3, 8, 13]) {
			const s = along(hip, t, -10);
			circle(p, s[0], s[1], 1.8, shade(def.shell, 0.25));
		}
	const belly = along(hip, 6.5, 2.5);
	ellipse(p, belly[0], belly[1], 4, 7.5, PLASTRON, angle);
	const belt = along(hip, 1.5, 0);
	ellipse(p, belt[0], belt[1], 6, 1.6, def.bandana, angle);

	limb(along(hip, 0, 1), pose.frontLeg, THIGH, SHIN, 4, skin, 2.4);

	// Head, mask, tails, and eyes.
	const head = along(shoulder, 5, 1.5);
	const [hx, hy] = head;
	const r = def.boss ? 6.5 : 6;
	circle(p, hx, hy, r, skin);
	for (let j = Math.floor(hy - 2.5); j < hy + 0.5; j++)
		for (let i = Math.floor(hx - r); i <= hx + r; i++)
			if ((i + 0.5 - hx) ** 2 + (j + 0.5 - hy) ** 2 <= r * r)
				set(p, i, j, def.bandana);
	const knot: [number, number] = [hx - r + 0.5, hy - 1];
	for (const spread of [0, 18]) {
		const [dx, dy] = toward(-(pose.tails + spread), 7);
		line(p, knot[0], knot[1], knot[0] + dx, knot[1] + dy, 2, def.bandana);
	}
	if (pose.eyes === "shut") rect(p, hx + 1, hy - 1, 4, 1, OUTLINE);
	else {
		rect(p, hx + 1, hy - 2, 4, 2, [250, 250, 250]);
		rect(p, hx + 3, hy - 2, 1, 2, OUTLINE);
	}
	if (def.boss) {
		line(p, hx + r - 1, hy + 1, hx + r + 2, hy + 3, 2, [214, 190, 90]);
		rect(p, hx + 1, hy + 3, 4, 1, OUTLINE);
	}

	limb(along(shoulder, -1, 1), pose.frontArm, UPPER_ARM, FOREARM, 3, skin, 2.2);
}

/** Every pose of every fighter: one row per fighter (in roster order), one column per pose (in POSE_NAMES order). */
export function sheet(): Pixels {
	const out = pixels(CELL * POSE_NAMES.length, CELL * FIGHTERS.length);
	for (const [row, def] of FIGHTERS.entries())
		for (const [col, name] of POSE_NAMES.entries()) {
			drawFighter(
				out,
				def,
				POSES[name],
				col * CELL + ORIGIN_X,
				row * CELL + FEET_Y,
			);
			outline(out, OUTLINE, col * CELL, row * CELL, CELL, CELL);
		}
	return out;
}

/** Where a fighter's feet sit inside its cell, for drawing it at its position. */
export const ANCHOR = { x: ORIGIN_X, y: FEET_Y } as const;

/** The pose to show for a fighter this frame. */
export function poseOf(f: Fighter, frame: number): PoseName {
	const back = f.facing > 0 ? LEFT : RIGHT;
	switch (f.action) {
		case "ko":
			return "ko";
		case "victory":
			return "victory";
		case "hitstun":
			return "hit";
		case "blockstun":
			return f.input & DOWN && f.y <= 0 ? "crouchBlock" : "block";
		case "air":
			return "jump";
		case "crouch":
			return f.input & back ? "crouchBlock" : "crouch";
		case "attack": {
			const move = f.def.moves[f.move ?? "punch"];
			const out =
				f.t >= move.startup &&
				f.t < move.startup + move.active + move.recovery / 2;
			switch (f.move) {
				case "punch":
					return out ? "punch1" : "punch0";
				case "kick":
					return out ? "kick1" : "kick0";
				case "special":
					return out ? "special1" : "special0";
				case "airKick":
					return f.t >= move.startup ? "airKick" : "jump";
				case "lowPunch":
					return out ? "lowPunch" : "crouch";
				case "lowKick":
					return out ? "lowKick" : "crouch";
				default:
					return "idle0";
			}
		}
		case "stand": {
			if (f.walking === 0)
				return Math.floor(frame / 30) % 2 ? "idle1" : "idle0";
			const step = Math.floor(f.t / 8) % 4;
			return `walk${f.walking > 0 ? step : 3 - step}` as PoseName;
		}
	}
}
