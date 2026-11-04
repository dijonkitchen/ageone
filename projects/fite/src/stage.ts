// Procedural stages, one per fighter, drawn with the same pixel primitives as the sprites: a dithered sky, a
// moon or sun, a skyline with lit windows, a rooftop wall, and a plank floor, all from a seeded generator.

import type { Rgb } from "./fighters";
import { circle, type Pixels, pixels, rect, set, shade } from "./pixels";
import { rng } from "./rng";
import { GROUND, HEIGHT, WIDTH } from "./sim";

interface Palette {
	name: string;
	skyTop: Rgb;
	skyLow: Rgb;
	orb: Rgb;
	city: Rgb;
	window: Rgb;
	wall: Rgb;
	floor: Rgb;
	stars: boolean;
}

export const STAGES: readonly Palette[] = [
	{
		name: "HARBOR DUSK",
		skyTop: [40, 36, 92],
		skyLow: [232, 120, 92],
		orb: [255, 214, 140],
		city: [44, 34, 70],
		window: [255, 200, 110],
		wall: [92, 64, 74],
		floor: [128, 92, 70],
		stars: false,
	},
	{
		name: "NEON ROOFTOP",
		skyTop: [10, 12, 36],
		skyLow: [56, 40, 110],
		orb: [230, 230, 250],
		city: [22, 20, 48],
		window: [120, 240, 255],
		wall: [60, 58, 90],
		floor: [84, 82, 110],
		stars: true,
	},
	{
		name: "TEMPLE YARD",
		skyTop: [120, 170, 230],
		skyLow: [250, 220, 170],
		orb: [255, 250, 220],
		city: [110, 120, 140],
		window: [250, 250, 230],
		wall: [170, 120, 90],
		floor: [196, 160, 110],
		stars: false,
	},
	{
		name: "SEWER GATE",
		skyTop: [20, 40, 36],
		skyLow: [60, 110, 90],
		orb: [200, 255, 210],
		city: [26, 50, 44],
		window: [160, 255, 170],
		wall: [64, 84, 76],
		floor: [80, 96, 86],
		stars: true,
	},
	{
		name: "IRON DOCK",
		skyTop: [30, 6, 10],
		skyLow: [180, 50, 30],
		orb: [255, 120, 60],
		city: [36, 14, 16],
		window: [255, 90, 40],
		wall: [70, 50, 50],
		floor: [90, 70, 66],
		stars: false,
	},
];

// 4x4 ordered dither, so gradients stay in a few flat colours.
const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];

const mix = (a: Rgb, b: Rgb, t: number): Rgb => [
	Math.round(a[0] + (b[0] - a[0]) * t),
	Math.round(a[1] + (b[1] - a[1]) * t),
	Math.round(a[2] + (b[2] - a[2]) * t),
];

export function drawStage(index: number): Pixels {
	const s = STAGES[index % STAGES.length] as Palette;
	const random = rng(1000 + index);
	const p = pixels(WIDTH, HEIGHT);
	const horizon = 132;
	const bands = 6;
	for (let y = 0; y < horizon; y++)
		for (let x = 0; x < WIDTH; x++) {
			const t =
				(y / horizon) * bands +
				(BAYER[(y % 4) * 4 + (x % 4)] as number) / 16 -
				0.5;
			set(
				p,
				x,
				y,
				mix(
					s.skyTop,
					s.skyLow,
					Math.min(bands, Math.max(0, Math.round(t))) / bands,
				),
			);
		}
	if (s.stars)
		for (let i = 0; i < 60; i++)
			set(
				p,
				random() * WIDTH,
				random() * horizon * 0.7,
				shade(s.orb, -random() * 0.4),
			);
	const orbX = 40 + random() * (WIDTH - 80);
	circle(p, orbX, 34, 13, shade(s.orb, -0.1));
	circle(p, orbX - 2, 32, 11, s.orb);
	// Skyline: two layers of buildings, the far one lighter.
	for (const [layer, base, tallest] of [
		[0.25, 132, 70],
		[0, 132, 50],
	] as const) {
		const color = shade(s.city, layer);
		for (let x = -10; x < WIDTH; ) {
			const w = 12 + Math.floor(random() * 22);
			const h = 18 + Math.floor(random() * tallest);
			rect(p, x, base - h, w, h, color);
			if (layer === 0)
				for (let wy = base - h + 4; wy < base - 4; wy += 6)
					for (let wx = x + 3; wx < x + w - 3; wx += 5)
						if (random() < 0.35) rect(p, wx, wy, 2, 3, s.window);
			x += w + Math.floor(random() * 6);
		}
	}
	// Rooftop wall with posts, then the floor.
	rect(p, 0, 132, WIDTH, GROUND - 132, s.wall);
	rect(p, 0, 132, WIDTH, 2, shade(s.wall, 0.25));
	for (let x = 4; x < WIDTH; x += 20)
		rect(p, x, 134, 3, GROUND - 134, shade(s.wall, -0.25));
	rect(p, 0, GROUND, WIDTH, HEIGHT - GROUND, s.floor);
	for (let y = GROUND; y < HEIGHT; y += 5) {
		rect(p, 0, y, WIDTH, 1, shade(s.floor, -0.2));
		const offset = ((y - GROUND) / 5) % 2 ? 14 : 0;
		for (let x = offset; x < WIDTH; x += 28)
			rect(p, x, y, 1, 5, shade(s.floor, -0.2));
	}
	rect(p, 0, GROUND, WIDTH, 1, shade(s.floor, 0.3));
	return p;
}
