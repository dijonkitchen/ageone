// Small 2D helpers for drawing body parts as smooth SVG paths. Coordinates are in body units (about a
// centimetre): y runs down from the top of the head (0) to the soles (about 176), and in the front view
// x runs from the body's right (negative) to its left (positive).

export type Point = [number, number];

const fmt = (n: number) => (Math.round(n * 100) / 100).toString();
const pt = ([x, y]: Point) => `${fmt(x)} ${fmt(y)}`;

/** A smooth closed curve through the points (a Catmull-Rom spline as cubic Béziers). */
export function smooth(points: Point[], tension = 1): string {
	const n = points.length;
	if (n < 3) throw new Error("a shape needs three or more points");
	const at = (i: number) => points[((i % n) + n) % n] as Point;
	let d = `M${pt(at(0))}`;
	for (let i = 0; i < n; i++) {
		const p0 = at(i - 1);
		const p1 = at(i);
		const p2 = at(i + 1);
		const p3 = at(i + 2);
		const c1: Point = [
			p1[0] + ((p2[0] - p0[0]) / 6) * tension,
			p1[1] + ((p2[1] - p0[1]) / 6) * tension,
		];
		const c2: Point = [
			p2[0] - ((p3[0] - p1[0]) / 6) * tension,
			p2[1] - ((p3[1] - p1[1]) / 6) * tension,
		];
		d += `C${pt(c1)} ${pt(c2)} ${pt(p2)}`;
	}
	return `${d}Z`;
}

/** A closed polygon with straight sides. */
export function polygon(points: Point[]): string {
	return `M${points.map(pt).join("L")}Z`;
}

export function ellipse([cx, cy]: Point, rx: number, ry: number): string {
	return `M${pt([cx - rx, cy])}A${fmt(rx)} ${fmt(ry)} 0 1 0 ${pt([cx + rx, cy])}A${fmt(rx)} ${fmt(ry)} 0 1 0 ${pt([cx - rx, cy])}Z`;
}

const sub = (a: Point, b: Point): Point => [a[0] - b[0], a[1] - b[1]];
const add = (a: Point, b: Point): Point => [a[0] + b[0], a[1] + b[1]];
const mul = (a: Point, k: number): Point => [a[0] * k, a[1] * k];
const unit = (a: Point): Point => {
	const l = Math.hypot(a[0], a[1]) || 1;
	return [a[0] / l, a[1] / l];
};
const perp = (a: Point): Point => [-a[1], a[0]];

/** A strip of the given width along a centreline (a strap muscle, a rib, a gut tube). */
export function band(
	line: Point[],
	width: number | number[],
	tension = 1,
): string {
	const w = (i: number) =>
		(Array.isArray(width)
			? (width[i] ?? width[width.length - 1] ?? 1)
			: width) / 2;
	const left: Point[] = [];
	const right: Point[] = [];
	for (let i = 0; i < line.length; i++) {
		const prev = line[Math.max(0, i - 1)] as Point;
		const next = line[Math.min(line.length - 1, i + 1)] as Point;
		const normal = perp(unit(sub(next, prev)));
		left.push(add(line[i] as Point, mul(normal, w(i))));
		right.push(add(line[i] as Point, mul(normal, -w(i))));
	}
	return smooth([...left, ...right.reverse()], tension);
}

/** A long bone from joint `a` to joint `b`: a shaft with wider, rounded ends. */
export function longBone(
	a: Point,
	b: Point,
	shaft: number,
	top: number,
	bottom: number,
): string {
	const dir = unit(sub(b, a));
	const n = perp(dir);
	const along = (p: Point, k: number) => add(p, mul(dir, k));
	const across = (p: Point, k: number) => add(p, mul(n, k));
	const mid = mul(add(a, b), 0.5);
	return smooth([
		along(a, -top * 0.75),
		across(along(a, -top * 0.35), top),
		across(along(a, top * 1.4), shaft / 2),
		across(mid, shaft * 0.45),
		across(along(b, -bottom * 1.4), shaft / 2),
		across(along(b, bottom * 0.35), bottom),
		along(b, bottom * 0.75),
		across(along(b, bottom * 0.35), -bottom),
		across(along(b, -bottom * 1.4), -shaft / 2),
		across(mid, -shaft * 0.45),
		across(along(a, top * 1.4), -shaft / 2),
		across(along(a, -top * 0.35), -top),
	]);
}

/** Several sub-shapes drawn as one structure (a group of small bones). */
export const join = (...paths: string[]) => paths.join("");

/** Mirror a path across the midline (x = 0): turns a right-side shape into the left-side one. */
export function mirrorPath(d: string): string {
	// Every coordinate pair follows a command letter or a previous pair; arcs carry radii and flags first.
	return d.replace(/([MLCA])([^MLCAZ]*)/g, (_, cmd: string, args: string) => {
		const nums = args
			.trim()
			.split(/[\s,]+/)
			.filter(Boolean)
			.map(Number);
		if (cmd === "A") {
			const out: number[] = [];
			for (let i = 0; i + 6 < nums.length + 1; i += 7) {
				const [rx, ry, rot, large, sweep, x, y] = nums.slice(
					i,
					i + 7,
				) as number[];
				out.push(
					rx as number,
					ry as number,
					-(rot as number),
					large as number,
					sweep ? 0 : 1,
					-(x as number),
					y as number,
				);
			}
			return `A${out.map(fmt).join(" ")}`;
		}
		return cmd + nums.map((v, i) => (i % 2 === 0 ? fmt(-v) : fmt(v))).join(" ");
	});
}

export const mirrorPoint = ([x, y]: Point): Point => [-x, y];

/** Rotate a point by `deg` degrees (SVG sense: clockwise on screen, y down) around `c`. */
export function rotate([x, y]: Point, deg: number, [cx, cy]: Point): Point {
	const r = (deg * Math.PI) / 180;
	const dx = x - cx;
	const dy = y - cy;
	return [
		cx + dx * Math.cos(r) - dy * Math.sin(r),
		cy + dx * Math.sin(r) + dy * Math.cos(r),
	];
}

/** Points of a path's commands, for bounds and tests. */
export function pathPoints(d: string): Point[] {
	const out: Point[] = [];
	for (const [, cmd, args] of d.matchAll(/([MLCA])([^MLCAZ]*)/g)) {
		const nums = (args as string)
			.trim()
			.split(/[\s,]+/)
			.filter(Boolean)
			.map(Number);
		if (cmd === "A") {
			for (let i = 0; i + 6 < nums.length + 1; i += 7)
				out.push([nums[i + 5] as number, nums[i + 6] as number]);
		} else
			for (let i = 0; i + 1 < nums.length; i += 2)
				out.push([nums[i] as number, nums[i + 1] as number]);
	}
	return out;
}

export function bounds(points: Point[]): {
	x: number;
	y: number;
	w: number;
	h: number;
} {
	const xs = points.map((p) => p[0]);
	const ys = points.map((p) => p[1]);
	const x = Math.min(...xs);
	const y = Math.min(...ys);
	return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
}
