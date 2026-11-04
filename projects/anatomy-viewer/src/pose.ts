// Where each skeleton segment's pivot ends up when segments are turned: the same nesting as the SVG
// groups, computed without a browser so tests (and later, movement) can check it.
import type { View } from "./data";
import type { Point } from "./geometry";
import { restPivot, segmentsIn } from "./svg";

/** An affine transform [a, b, c, d, e, f], as in SVG's matrix(). */
type Matrix = [number, number, number, number, number, number];
const IDENTITY: Matrix = [1, 0, 0, 1, 0, 0];

const multiply = (m: Matrix, n: Matrix): Matrix => [
	m[0] * n[0] + m[2] * n[1],
	m[1] * n[0] + m[3] * n[1],
	m[0] * n[2] + m[2] * n[3],
	m[1] * n[2] + m[3] * n[3],
	m[0] * n[4] + m[2] * n[5] + m[4],
	m[1] * n[4] + m[3] * n[5] + m[5],
];

function rotation(deg: number, [cx, cy]: Point): Matrix {
	const r = (deg * Math.PI) / 180;
	const cos = Math.cos(r);
	const sin = Math.sin(r);
	return [
		cos,
		sin,
		-sin,
		cos,
		cx - cos * cx + sin * cy,
		cy - sin * cx - cos * cy,
	];
}

export const apply = (m: Matrix, [x, y]: Point): Point => [
	m[0] * x + m[2] * y + m[4],
	m[1] * x + m[3] * y + m[5],
];

/** Each segment's transform from rest to posed, and its pivot after posing. */
export function pose(
	view: View,
	angles: Record<string, number> = {},
): Map<string, { matrix: Matrix; pivot: Point }> {
	const shown = segmentsIn(view);
	const out = new Map<string, { matrix: Matrix; pivot: Point }>();
	const visit = (parent: string | null, inherited: Matrix) => {
		for (const s of shown.filter((x) => x.parent === parent)) {
			const rest = restPivot(s, view);
			const matrix = multiply(inherited, rotation(angles[s.id] ?? 0, rest));
			out.set(s.id, { matrix, pivot: apply(inherited, rest) });
			visit(s.id, matrix);
		}
	};
	visit(null, IDENTITY);
	return out;
}
