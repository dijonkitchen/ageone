// Generated tile sets: a seeded draw of 72 valid tiles that stays close to the base game's balance.
import { analyse, canonical, catalog, groups, parseCode } from "./tiles";

/**
 * The base game's 72 tiles by kind, as commonly listed (letters A to X), used only as the balance reference.
 * Recalled from published tile lists, not checked against a rulebook; see the stack decision record.
 */
export const BASE: Record<string, number> = {
	"FFRF+M": 2,
	"FFFF+M": 4,
	"CCCC+S": 1,
	CRFR: 4, // includes the start tile
	CFFF: 5,
	"CFCF+S": 2,
	CFCF: 1,
	"CFCF+X": 3,
	"CCFF+X": 2,
	CRRF: 3,
	CFRR: 3,
	"CRRR+J": 3,
	"CCFF+S": 2,
	CCFF: 3,
	"CCRR+S": 2,
	CCRR: 3,
	"CCFC+S": 1,
	CCFC: 3,
	"CCRC+S": 2,
	CCRC: 1,
	RFRF: 8,
	FFRR: 9,
	"FRRR+J": 4,
	"RRRR+J": 1,
};

export const START = "CRFR";
export const SET_SIZE = 72;

export interface Stats {
	tiles: number;
	edges: { C: number; R: number; F: number }; // shares of all edges
	monasteries: number;
	shields: number;
	roadEnds: number; // tiles on which a road ends (at a city, monastery, or junction)
	caps: number; // tiles with a one-edge city, which closes a city
}

export function stats(tiles: string[]): Stats {
	const count = { C: 0, R: 0, F: 0 };
	let monasteries = 0;
	let shields = 0;
	let roadEnds = 0;
	let caps = 0;
	for (const code of tiles) {
		const s = parseCode(code);
		for (const e of s.edges) count[e]++;
		const g = groups(s);
		if (typeof g === "string") throw new Error(`bad tile code ${code}: ${g}`);
		if (s.monastery) monasteries++;
		if (s.shield) shields++;
		if (g.ends) roadEnds++;
		if (g.cities.some((c) => c.length === 1)) caps++;
	}
	const n = tiles.length * 4;
	return {
		tiles: tiles.length,
		edges: { C: count.C / n, R: count.R / n, F: count.F / n },
		monasteries,
		shields,
		roadEnds,
		caps,
	};
}

export const baseTiles = (): string[] =>
	Object.entries(BASE).flatMap(([code, n]) =>
		Array<string>(n).fill(canonical(code)),
	);

const BASE_STATS = stats(baseTiles());

/** How far a generated set may drift from the base set. */
export const LIMITS = {
	edgeShare: 0.03,
	monasteries: [5, 7],
	shields: [8, 12],
	roadEnds: [BASE_STATS.roadEnds - 3, BASE_STATS.roadEnds + 3],
	caps: [BASE_STATS.caps - 4, BASE_STATS.caps + 4],
} as const;

export const baseStats = (): Stats => BASE_STATS;

/** Reasons a set breaks the balance limits; empty when it is within them. */
export function balance(tiles: string[]): string[] {
	const s = stats(tiles);
	const out: string[] = [];
	if (s.tiles !== SET_SIZE) out.push(`${s.tiles} tiles, not ${SET_SIZE}`);
	for (const e of ["C", "R", "F"] as const)
		if (Math.abs(s.edges[e] - BASE_STATS.edges[e]) > LIMITS.edgeShare)
			out.push(
				`${e} edge share ${s.edges[e].toFixed(3)} is more than ${LIMITS.edgeShare} from ${BASE_STATS.edges[e].toFixed(3)}`,
			);
	const range = (name: keyof typeof LIMITS, v: number) => {
		const [lo, hi] = LIMITS[name] as readonly [number, number];
		if (v < lo || v > hi) out.push(`${name} ${v} is outside ${lo} to ${hi}`);
	};
	range("monasteries", s.monasteries);
	range("shields", s.shields);
	range("roadEnds", s.roadEnds);
	range("caps", s.caps);
	return out;
}

/** A small, fast, seeded random generator (mulberry32): the same seed always gives the same numbers. */
export function random(seed: number): () => number {
	let a = seed >>> 0;
	return () => {
		a = (a + 0x6d2b79f5) >>> 0;
		let t = a;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

/** Kinds to draw from, weighted by their base count, with every other valid kind given a small weight. */
const WEIGHTS: [string, number][] = (() => {
	const base = new Map(Object.entries(BASE).map(([c, n]) => [canonical(c), n]));
	return catalog().map((code) => [code, base.get(code) ?? 0.75]);
})();

function pick(rand: () => number): string {
	const total = WEIGHTS.reduce((a, [, w]) => a + w, 0);
	let x = rand() * total;
	for (const [code, w] of WEIGHTS) {
		x -= w;
		if (x < 0) return code;
	}
	return (WEIGHTS[WEIGHTS.length - 1] as [string, number])[0];
}

/**
 * The tile set for a seed: the start tile first, then 71 tiles in draw order.
 * Draws whole sets until one is within the balance limits, so every set it returns is.
 */
export function generate(seed: number): string[] {
	const rand = random(seed);
	for (let attempt = 0; attempt < 100_000; attempt++) {
		const rest = Array.from({ length: SET_SIZE - 1 }, () => pick(rand));
		const tiles = [START, ...rest];
		if (balance(tiles).length === 0) {
			// Shuffle the draw order (Fisher-Yates), keeping the start tile first.
			for (let i = rest.length - 1; i > 0; i--) {
				const j = Math.floor(rand() * (i + 1));
				[rest[i], rest[j]] = [rest[j] as string, rest[i] as string];
			}
			return [START, ...rest];
		}
	}
	throw new Error(`no balanced set found for seed ${seed}`);
}

/** Every tile in the set is a valid layout. */
export const allValid = (tiles: string[]): boolean =>
	tiles.every((t) => typeof analyse(t) !== "string");
