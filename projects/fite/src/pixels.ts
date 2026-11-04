// A pixel buffer and the few drawing primitives the sprites and stages are built from. Pure: no canvas, so the
// sprite sheet can be generated and compared headless, and the page copies the same pixels into a canvas.

import type { Rgb } from "./fighters";

export interface Pixels {
	width: number;
	height: number;
	data: Uint8ClampedArray; // RGBA, row by row
}

export function pixels(width: number, height: number): Pixels {
	return { width, height, data: new Uint8ClampedArray(width * height * 4) };
}

export function set(
	p: Pixels,
	x: number,
	y: number,
	c: Rgb,
	alpha = 255,
): void {
	const xi = Math.floor(x);
	const yi = Math.floor(y);
	if (xi < 0 || yi < 0 || xi >= p.width || yi >= p.height) return;
	const i = (yi * p.width + xi) * 4;
	p.data[i] = c[0];
	p.data[i + 1] = c[1];
	p.data[i + 2] = c[2];
	p.data[i + 3] = alpha;
}

export function opaque(p: Pixels, x: number, y: number): boolean {
	if (x < 0 || y < 0 || x >= p.width || y >= p.height) return false;
	return (p.data[(y * p.width + x) * 4 + 3] ?? 0) > 0;
}

export function rect(
	p: Pixels,
	x: number,
	y: number,
	w: number,
	h: number,
	c: Rgb,
): void {
	for (let j = Math.round(y); j < Math.round(y + h); j++)
		for (let i = Math.round(x); i < Math.round(x + w); i++) set(p, i, j, c);
}

/** A filled ellipse with radii rx, ry, turned by `angle` radians. */
export function ellipse(
	p: Pixels,
	cx: number,
	cy: number,
	rx: number,
	ry: number,
	c: Rgb,
	angle = 0,
): void {
	const r = Math.ceil(Math.max(rx, ry));
	const cos = Math.cos(angle);
	const sin = Math.sin(angle);
	for (let j = Math.floor(cy - r); j <= Math.ceil(cy + r); j++)
		for (let i = Math.floor(cx - r); i <= Math.ceil(cx + r); i++) {
			const dx = i + 0.5 - cx;
			const dy = j + 0.5 - cy;
			const u = dx * cos + dy * sin;
			const v = -dx * sin + dy * cos;
			if ((u * u) / (rx * rx) + (v * v) / (ry * ry) <= 1) set(p, i, j, c);
		}
}

export const circle = (
	p: Pixels,
	cx: number,
	cy: number,
	r: number,
	c: Rgb,
): void => ellipse(p, cx, cy, r, r, c);

/** A line `width` pixels thick with round ends. */
export function line(
	p: Pixels,
	x0: number,
	y0: number,
	x1: number,
	y1: number,
	width: number,
	c: Rgb,
): void {
	const steps = Math.max(1, Math.ceil(Math.hypot(x1 - x0, y1 - y0) * 2));
	for (let s = 0; s <= steps; s++) {
		const t = s / steps;
		circle(p, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, width / 2, c);
	}
}

/** Paint every empty pixel that touches a filled one, inside the box (x, y, w, h). */
export function outline(
	p: Pixels,
	c: Rgb,
	x = 0,
	y = 0,
	w = p.width,
	h = p.height,
): void {
	const edge: [number, number][] = [];
	for (let j = y; j < y + h; j++)
		for (let i = x; i < x + w; i++)
			if (
				!opaque(p, i, j) &&
				((i > x && opaque(p, i - 1, j)) ||
					(i < x + w - 1 && opaque(p, i + 1, j)) ||
					(j > y && opaque(p, i, j - 1)) ||
					(j < y + h - 1 && opaque(p, i, j + 1)))
			)
				edge.push([i, j]);
	for (const [i, j] of edge) set(p, i, j, c);
}

/** Lighten (positive) or darken (negative) a colour by a fraction. */
export function shade(c: Rgb, by: number): Rgb {
	const f = (v: number) =>
		Math.round(by > 0 ? v + (255 - v) * by : v * (1 + by));
	return [f(c[0]), f(c[1]), f(c[2])];
}

/** Copy `src` into `dst` at (x, y), skipping transparent pixels. */
export function blit(dst: Pixels, src: Pixels, x: number, y: number): void {
	for (let j = 0; j < src.height; j++)
		for (let i = 0; i < src.width; i++) {
			const k = (j * src.width + i) * 4;
			if (!src.data[k + 3]) continue;
			set(dst, x + i, y + j, [
				src.data[k] ?? 0,
				src.data[k + 1] ?? 0,
				src.data[k + 2] ?? 0,
			]);
		}
}
