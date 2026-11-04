// The structure data (data/anatomy.json): names, descriptions, relations, and skeleton segments, keyed by
// FMA ids. Paired structures have one entry with an id per side; each side is drawn as its own shape.
import raw from "../data/anatomy.json";

export type View = "front" | "back" | "side";
export const VIEWS: View[] = ["front", "back", "side"];
export type Side = "right" | "left";

export interface Structure {
	id: string;
	name: string;
	latin: string;
	latinSource?: "TA";
	synonyms: string[];
	system: "skeleton" | "muscles" | "organs" | "skin";
	count: number;
	sides?: Record<Side, string>;
	description: string;
	joints?: string[];
	origin?: string[];
	insertion?: string[];
	action?: string;
	nerve?: string;
	neighbors?: string[];
	notDrawn?: string;
}

export interface Motion {
	view: "front" | "side" | null; // null: a turn about the bone's own axis, not shown in a 2D view
	min: number; // degrees of SVG rotation in that view (positive turns clockwise on screen)
	max: number;
	negative: string;
	positive: string;
}

export interface Segment {
	id: string;
	name: string;
	parent: string | null;
	joint?: string;
	pivot: { front: [number, number]; side: [number, number] };
	motion: Motion[];
	approximate?: boolean;
	bones: string[];
}

export interface Layer {
	id: string;
	name: string;
	planned?: boolean;
}

export interface Source {
	id: string;
	name: string;
	url: string;
	license: string;
	use: string;
}

interface Data {
	about: string;
	sources: Source[];
	layers: Layer[];
	segments: Segment[];
	structures: Structure[];
}

export const DATA = raw as unknown as Data;
export const STRUCTURES = DATA.structures;
export const SEGMENTS = DATA.segments;
export const LAYERS = DATA.layers;

/** A drawable or data id: a structure's own id or one of its side ids. */
export interface Part {
	id: string;
	structure: Structure;
	side: Side | null;
}

const parts = new Map<string, Part>();
for (const s of STRUCTURES) {
	parts.set(s.id, { id: s.id, structure: s, side: null });
	if (s.sides)
		for (const side of ["right", "left"] as Side[])
			parts.set(s.sides[side], { id: s.sides[side], structure: s, side });
}
const byName = new Map(STRUCTURES.map((s) => [s.name, s]));

export const part = (id: string): Part | undefined => parts.get(id);
export const allParts = (): Part[] => [...parts.values()];

export function structureNamed(name: string): Structure {
	const s = byName.get(name);
	if (!s) throw new Error(`no structure named ${name}`);
	return s;
}

/** The id to draw for a structure on one side (its side id when paired). */
export function drawnId(name: string, side: Side | null): string {
	const s = structureNamed(name);
	if (!s.sides) return s.id;
	if (!side) throw new Error(`${name} is paired: say which side`);
	return s.sides[side];
}

export function label(p: Part): string {
	return p.side
		? `${p.side === "right" ? "Right" : "Left"} ${p.structure.name.toLowerCase()}`
		: p.structure.name;
}

export const SYSTEM_NAMES: Record<Structure["system"], string> = {
	skeleton: "Skeletal system",
	muscles: "Muscular system",
	organs: "Organs",
	skin: "Integumentary system",
};

/** Related structures, by kind, for the details panel. */
export function relations(s: Structure): { kind: string; ids: string[] }[] {
	const out: { kind: string; ids: string[] }[] = [];
	if (s.joints?.length) out.push({ kind: "Joins", ids: s.joints });
	if (s.origin?.length) out.push({ kind: "Origin", ids: s.origin });
	if (s.insertion?.length) out.push({ kind: "Insertion", ids: s.insertion });
	if (s.neighbors?.length) out.push({ kind: "Neighbors", ids: s.neighbors });
	return out;
}

const normalize = (t: string) =>
	t
		.toLowerCase()
		.normalize("NFD")
		.replace(/[̀-ͯ]/g, "")
		.replace(/[^a-z0-9 ]+/g, " ")
		.replace(/\s+/g, " ")
		.trim();

/** Structures matching a query by common name, Latin name, or synonym; best matches first. */
export function search(query: string, limit = 12): Structure[] {
	const q = normalize(query);
	if (!q) return [];
	const scored: [number, Structure][] = [];
	for (const s of STRUCTURES) {
		const names = [s.name, s.latin, ...s.synonyms].map(normalize);
		let best = 0;
		for (const n of names) {
			if (n === q) best = Math.max(best, 4);
			else if (n.startsWith(q)) best = Math.max(best, 3);
			else if (n.split(" ").some((w) => w.startsWith(q)))
				best = Math.max(best, 2);
			else if (n.includes(q)) best = Math.max(best, 1);
		}
		if (best) scored.push([best, s]);
	}
	return scored
		.sort((a, b) => b[0] - a[0] || a[1].name.localeCompare(b[1].name))
		.slice(0, limit)
		.map(([, s]) => s);
}
