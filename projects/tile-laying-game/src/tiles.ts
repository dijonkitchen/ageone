// Tiles: a short text code, the geometry it describes, and the features (cities, roads, fields, monastery) that
// geometry has. The same geometry draws the tile and decides its fields, so what you see is what scores.
//
// Code: four edge letters clockwise from the top (N, E, S, W), each C (city), R (road), or F (field), then flags:
//   +M  a monastery in the centre (no cities; at most one road, which ends at it)
//   +S  a shield on the city (one city of two or more edges)
//   +J  the roads (three or four) end at a junction in the centre
//   +X  each city edge is its own small city, not one city
//   +D  two roads both end in the city instead of joining each other
// Otherwise all city edges form one city, two road edges are one road, and a single road ends in the city or
// monastery. For example "CRFR" is a city edge on top with a straight road across, "FRRR+J" a three-way junction.

export type Edge = "C" | "R" | "F";
export type Side = 0 | 1 | 2 | 3; // N, E, S, W

export interface TileSpec {
	edges: [Edge, Edge, Edge, Edge];
	monastery: boolean;
	shield: boolean;
	junction: boolean;
	separate: boolean;
	deadEnds: boolean;
}

export interface Features {
	cities: { sides: Side[]; shield: boolean; anchor: Point }[];
	roads: { sides: Side[]; anchor: Point }[]; // a road with one side ends on this tile
	fields: { ports: number[]; cities: number[]; anchor: Point }[]; // ports: side * 3 + 0..2, clockwise
	monastery: { anchor: Point } | null;
}

export type Point = [number, number]; // within the tile, 0..1, y down

const FLAGS = {
	M: "monastery",
	S: "shield",
	J: "junction",
	X: "separate",
	D: "deadEnds",
} as const;

export function parseCode(code: string): TileSpec {
	const [edges = "", ...flags] = code.split("+");
	if (!/^[CRF]{4}$/.test(edges))
		throw new Error(`bad tile code ${code}: needs four edges of C, R, or F`);
	const spec: TileSpec = {
		edges: [...edges] as TileSpec["edges"],
		monastery: false,
		shield: false,
		junction: false,
		separate: false,
		deadEnds: false,
	};
	for (const f of flags) {
		const key = FLAGS[f as keyof typeof FLAGS];
		if (!key || spec[key])
			throw new Error(`bad tile code ${code}: unknown or repeated flag +${f}`);
		spec[key] = true;
	}
	return spec;
}

export function formatCode(s: TileSpec): string {
	let code = s.edges.join("");
	for (const [letter, key] of Object.entries(FLAGS))
		if (s[key]) code += `+${letter}`;
	return code;
}

const sidesOf = (s: TileSpec, e: Edge): Side[] =>
	([0, 1, 2, 3] as Side[]).filter((i) => s.edges[i] === e);

/** City groups and road groups the code describes, or a reason it describes none. */
export function groups(s: TileSpec):
	| {
			cities: Side[][];
			roads: Side[][];
			ends: "city" | "monastery" | "junction" | null;
	  }
	| string {
	const c = sidesOf(s, "C");
	const r = sidesOf(s, "R");
	if (s.monastery && c.length) return "a monastery tile has no city";
	if (s.monastery && r.length > 1) return "a monastery has at most one road";
	if (s.separate && c.length < 2) return "+X needs two or more city edges";
	if (s.shield && (s.separate || c.length < 2))
		return "+S needs one city of two or more edges";
	if (s.junction && r.length < 3) return "+J needs three or four roads";
	if (s.deadEnds && (r.length !== 2 || !c.length))
		return "+D needs two roads and a city";
	if (!s.junction && r.length > 2)
		return "three or four roads need a junction (+J)";
	const cities = !c.length ? [] : s.separate ? c.map((x) => [x]) : [c];
	let roads: Side[][];
	let ends: "city" | "monastery" | "junction" | null = null;
	if (s.junction) {
		roads = r.map((x) => [x]);
		ends = "junction";
	} else if (r.length === 2 && !s.deadEnds) roads = [r];
	else {
		roads = r.map((x) => [x]);
		if (r.length) ends = s.monastery ? "monastery" : "city";
		if (ends === "city" && !c.length)
			return "a road that ends needs a city, monastery, or junction to end at";
	}
	return { cities, roads, ends };
}

// Geometry. Each side has a frame in which that side is on top: toFrame maps tile coordinates into it.
function toFrame(side: number, x: number, y: number): Point {
	switch (side) {
		case 1:
			return [y, 1 - x];
		case 2:
			return [1 - x, 1 - y];
		case 3:
			return [1 - y, x];
		default:
			return [x, y];
	}
}

function fromFrame(side: number, x: number, y: number): Point {
	switch (side) {
		case 1:
			return [1 - y, x];
		case 2:
			return [1 - x, 1 - y];
		case 3:
			return [y, 1 - x];
		default:
			return [x, y];
	}
}

const cap = (side: number, x: number, y: number) => {
	const [u, v] = toFrame(side, x, y);
	return v < 0.28 - 1.4 * (u - 0.5) ** 2;
};
const ROAD = 0.065;
const JUNCTION = 0.1;
const MONASTERY = 0.17;

function inCity(sides: Side[], x: number, y: number): boolean {
	const n = sides.length;
	if (n === 4) return true;
	if (n === 1) return cap(sides[0] as Side, x, y);
	if (n === 3) {
		const missing = ([0, 1, 2, 3] as Side[]).find(
			(s) => !sides.includes(s),
		) as Side;
		return !cap(missing, x, y);
	}
	const [a, b] = sides as [Side, Side];
	if ((a + 2) % 4 === b) {
		const [u] = toFrame(a, x, y);
		return cap(a, x, y) || cap(b, x, y) || Math.abs(u - 0.5) < 0.2;
	}
	// Two neighbouring sides: the half of the tile on their shared corner's side of the diagonal.
	const first = (b - a + 4) % 4 === 1 ? a : b;
	const [u, v] = toFrame(first, x, y);
	return v < u;
}

function onRoad(sides: Side[], x: number, y: number): boolean {
	if (sides.length === 1) {
		const [u, v] = toFrame(sides[0] as Side, x, y);
		return Math.abs(u - 0.5) < ROAD && v < 0.5 + ROAD;
	}
	const [a, b] = sides as [Side, Side];
	if ((a + 2) % 4 === b) {
		const [u] = toFrame(a, x, y);
		return Math.abs(u - 0.5) < ROAD;
	}
	// A quarter circle around the two sides' shared corner.
	const first = (b - a + 4) % 4 === 1 ? a : b;
	const [u, v] = toFrame(first, x, y);
	return Math.abs(Math.hypot(u - 1, v) - 0.5) < ROAD;
}

/** What is at a point of a tile: used both to find the features and to draw the tile. */
export type Cell =
	| { kind: "city"; group: number }
	| { kind: "road"; group: number }
	| { kind: "junction" }
	| { kind: "monastery" }
	| { kind: "field" };

export function classifier(code: string): (x: number, y: number) => Cell {
	const s = parseCode(code);
	const g = groups(s);
	if (typeof g === "string") throw new Error(`bad tile code ${code}: ${g}`);
	return (x, y) => {
		for (const [i, c] of g.cities.entries())
			if (inCity(c, x, y)) return { kind: "city", group: i };
		if (
			s.monastery &&
			Math.abs(x - 0.5) < MONASTERY &&
			Math.abs(y - 0.5) < MONASTERY
		)
			return { kind: "monastery" };
		if (
			s.junction &&
			Math.abs(x - 0.5) < JUNCTION &&
			Math.abs(y - 0.5) < JUNCTION
		)
			return { kind: "junction" };
		for (const [i, r] of g.roads.entries())
			if (onRoad(r, x, y)) return { kind: "road", group: i };
		return { kind: "field" };
	};
}

const N = 48; // raster size for finding features

/** Where port `p` (side * 3 + 0..2, clockwise) sits, just inside the edge. */
export function portPoint(p: number): Point {
	const side = Math.floor(p / 3);
	return fromFrame(side, ((p % 3) * 2 + 1) / 6, 0.5 / N);
}

const pixel = ([x, y]: Point): number =>
	Math.min(N - 1, Math.floor(y * N)) * N + Math.min(N - 1, Math.floor(x * N));

function components(n: number, inSet: (i: number) => boolean): Int32Array {
	const label = new Int32Array(n * n).fill(-1);
	let next = 0;
	for (let start = 0; start < n * n; start++) {
		if (label[start] !== -1 || !inSet(start)) continue;
		const stack = [start];
		label[start] = next;
		while (stack.length) {
			const i = stack.pop() as number;
			const x = i % n;
			const y = Math.floor(i / n);
			for (const [dx, dy] of [
				[1, 0],
				[-1, 0],
				[0, 1],
				[0, -1],
			] as const) {
				const nx = x + dx;
				const ny = y + dy;
				const j = ny * n + nx;
				if (
					nx >= 0 &&
					ny >= 0 &&
					nx < n &&
					ny < n &&
					label[j] === -1 &&
					inSet(j)
				) {
					label[j] = next;
					stack.push(j);
				}
			}
		}
		next++;
	}
	return label;
}

/**
 * Where a meeple stands on a feature: the cell deepest inside it (farthest from anything else and from the
 * tile's edge), the one nearest the average among equals, so the anchor is inside and clear of its neighbours.
 */
const center = (cells: number[]): Point => {
	const inside = new Set(cells);
	const depth = new Int32Array(N * N).fill(-1);
	let frontier: number[] = [];
	for (let i = 0; i < N * N; i++) {
		const x = i % N;
		const y = Math.floor(i / N);
		if (!inside.has(i) || x === 0 || y === 0 || x === N - 1 || y === N - 1) {
			depth[i] = 0;
			frontier.push(i);
		}
	}
	for (let d = 1; frontier.length; d++) {
		const next: number[] = [];
		for (const i of frontier) {
			const x = i % N;
			for (const j of [i - 1, i + 1, i - N, i + N])
				if (
					j >= 0 &&
					j < N * N &&
					Math.abs((j % N) - x) <= 1 &&
					depth[j] === -1
				) {
					depth[j] = d;
					next.push(j);
				}
		}
		frontier = next;
	}
	const avg = cells
		.reduce<[number, number]>(
			(a, i) => [a[0] + (i % N), a[1] + Math.floor(i / N)],
			[0, 0],
		)
		.map((v) => v / cells.length);
	// Deep enough to clear a meeple, then as central as possible.
	const deepest = Math.max(...cells.map((i) => depth[i] as number));
	const enough = Math.min(deepest, Math.round(N * 0.12));
	let best = cells[0] as number;
	let bestD = Number.POSITIVE_INFINITY;
	for (const i of cells) {
		if ((depth[i] as number) < enough) continue;
		const d =
			((i % N) - (avg[0] as number)) ** 2 +
			(Math.floor(i / N) - (avg[1] as number)) ** 2;
		if (d < bestD) {
			bestD = d;
			best = i;
		}
	}
	return [((best % N) + 0.5) / N, (Math.floor(best / N) + 0.5) / N];
};

const cache = new Map<string, Features | string>();

/** The tile's features at rotation 0, or why the code is not a valid tile. */
export function analyse(code: string): Features | string {
	const hit = cache.get(code);
	if (hit !== undefined) return hit;
	const result = analyseUncached(code);
	cache.set(code, result);
	return result;
}

export function features(code: string): Features {
	const f = analyse(code);
	if (typeof f === "string") throw new Error(`bad tile code ${code}: ${f}`);
	return f;
}

function analyseUncached(code: string): Features | string {
	let s: TileSpec;
	try {
		s = parseCode(code);
	} catch (e) {
		return (e as Error).message;
	}
	const g = groups(s);
	if (typeof g === "string") return g;
	const at = (i: number): Point => [
		((i % N) + 0.5) / N,
		(Math.floor(i / N) + 0.5) / N,
	];
	const cell = classifier(code);
	const cells = Array.from({ length: N * N }, (_, i) => cell(...at(i)));
	const adjacent = (a: (i: number) => boolean, b: (i: number) => boolean) => {
		for (let i = 0; i < N * N; i++) {
			if (!a(i)) continue;
			const x = i % N;
			for (const j of [i - 1, i + 1, i - N, i + N])
				if (j >= 0 && j < N * N && Math.abs((j % N) - x) <= 1 && b(j))
					return true;
		}
		return false;
	};

	// Cities: each one connected, covering exactly its own edges, and not touching the others.
	const cities: Features["cities"] = [];
	for (const [k, sides] of g.cities.entries()) {
		const mine = (i: number) => {
			const c = cells[i] as Cell;
			return c.kind === "city" && c.group === k;
		};
		const pixels = [...cells.keys()].filter(mine);
		const label = components(N, mine);
		if (new Set(pixels.map((i) => label[i])).size !== 1)
			return `city ${k} is in pieces`;
		for (let p = 0; p < 12; p++)
			if (
				mine(pixel(portPoint(p))) !== sides.includes(Math.floor(p / 3) as Side)
			)
				return `city ${k} doesn't match its edges`;
		for (let other = k + 1; other < g.cities.length; other++)
			if (
				adjacent(
					mine,
					(i) =>
						(cells[i] as Cell).kind === "city" &&
						(cells[i] as { group: number }).group === other,
				)
			)
				return "two separate cities touch";
		cities.push({ sides, shield: s.shield, anchor: center(pixels) });
	}

	// Roads: each one connected, on its edges' middles, ending where it should, and crossing nothing.
	const roads: Features["roads"] = [];
	for (const [k, sides] of g.roads.entries()) {
		const raw = (i: number) => onRoad(sides, ...at(i));
		const pixels = [...cells.keys()].filter(raw);
		const label = components(N, raw);
		if (new Set(pixels.map((i) => label[i])).size !== 1)
			return `road ${k} is in pieces`;
		for (let p = 0; p < 12; p++) {
			const onIt = raw(pixel(portPoint(p)));
			if (p % 3 === 1 && onIt !== sides.includes(Math.floor(p / 3) as Side))
				return `road ${k} doesn't match its edges`;
		}
		const ends = sides.length === 1 ? g.ends : null;
		for (const i of pixels) {
			const c = cells[i] as Cell;
			if (c.kind === "city" && ends !== "city")
				return `road ${k} runs into a city`;
			if (c.kind === "road" && c.group !== k)
				return `road ${k} crosses another road`;
			if (c.kind === "monastery" && ends !== "monastery")
				return `road ${k} runs into the monastery`;
		}
		if (ends) {
			const target = ends === "city" ? "city" : ends;
			if (!pixels.some((i) => (cells[i] as Cell).kind === target))
				return `road ${k} doesn't reach its ${ends}`;
		}
		const visible = pixels.filter((i) => (cells[i] as Cell).kind === "road");
		roads.push({ sides, anchor: center(visible.length ? visible : pixels) });
	}

	// Fields: what is left, split by cities and roads; every piece must reach the tile's edge.
	const free = (i: number) => (cells[i] as Cell).kind === "field";
	const label = components(N, free);
	const regions = new Map<number, number[]>();
	for (let p = 0; p < 12; p++) {
		const side = Math.floor(p / 3);
		const edge = s.edges[side];
		const isField = edge === "F" || (edge === "R" && p % 3 !== 1);
		const i = pixel(portPoint(p));
		if (isField !== free(i))
			return `edge ${side} doesn't match the drawing at port ${p}`;
		if (!isField) continue;
		const r = label[i] as number;
		regions.set(r, [...(regions.get(r) ?? []), p]);
	}
	const all = new Set([...cells.keys()].filter(free).map((i) => label[i]));
	if (all.size !== regions.size)
		return "a field is shut in, away from every edge";
	const fields: Features["fields"] = [...regions.entries()].map(
		([r, ports]) => {
			const mine = (i: number) => label[i] === r;
			const touching = cities.flatMap((_, k) =>
				adjacent(
					mine,
					(i) =>
						(cells[i] as Cell).kind === "city" &&
						(cells[i] as { group: number }).group === k,
				)
					? [k]
					: [],
			);
			return {
				ports,
				cities: touching,
				anchor: center([...cells.keys()].filter(mine)),
			};
		},
	);
	fields.sort((a, b) => (a.ports[0] as number) - (b.ports[0] as number));
	return {
		cities,
		roads,
		fields,
		monastery: s.monastery ? { anchor: [0.5, 0.5] } : null,
	};
}

/** Rotate a point of the tile a quarter turn clockwise, `r` times. */
export function rotatePoint([x, y]: Point, r: number): Point {
	let p: Point = [x, y];
	for (let i = 0; i < ((r % 4) + 4) % 4; i++) p = [1 - p[1], p[0]];
	return p;
}

/** The tile's edge on `side` when it is turned `r` quarter turns clockwise. */
export const edgeAt = (code: string, r: number, side: Side): Edge =>
	parseCode(code).edges[(side - r + 8) % 4] as Edge;
export const rotateSide = (side: Side, r: number): Side =>
	((side + r) % 4) as Side;
export const rotatePort = (port: number, r: number): number =>
	(port + 3 * r) % 12;

/** The same tile in its smallest rotation, so equal tiles have equal codes. */
export function canonical(code: string): string {
	const s = parseCode(code);
	const options = [0, 1, 2, 3].map((r) =>
		formatCode({
			...s,
			edges: [0, 1, 2, 3].map((i) => s.edges[(i + r) % 4]) as TileSpec["edges"],
		}),
	);
	return options.sort()[0] as string;
}

/** Every valid tile up to rotation. */
export function catalog(): string[] {
	const out = new Set<string>();
	const letters: Edge[] = ["C", "R", "F"];
	for (const a of letters)
		for (const b of letters)
			for (const c of letters)
				for (const d of letters)
					for (let flags = 0; flags < 32; flags++) {
						const s: TileSpec = {
							edges: [a, b, c, d],
							monastery: !!(flags & 1),
							shield: !!(flags & 2),
							junction: !!(flags & 4),
							separate: !!(flags & 8),
							deadEnds: !!(flags & 16),
						};
						const code = canonical(formatCode(s));
						if (typeof analyse(code) !== "string") out.add(code);
					}
	return [...out].sort();
}
