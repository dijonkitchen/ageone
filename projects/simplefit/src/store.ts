// The app's data and every change to it, as pure functions; app.ts keeps the result in localStorage.

import { type Day, isDay } from "./dates";
import { DEFAULT_TARGETS, type Sex } from "./formulas";

export const KINDS = ["zone2", "zone4", "strength", "rhr", "vo2max"] as const;
export type Kind = (typeof KINDS)[number];

/** How each kind is logged and summed. */
export const KIND_INFO: Record<
	Kind,
	{
		label: string;
		unit: string;
		weekly: "sum" | "latest";
		min: number;
		max: number;
	}
> = {
	zone2: { label: "Zone 2", unit: "min", weekly: "sum", min: 1, max: 600 },
	zone4: {
		label: "Zone 4 intervals",
		unit: "min",
		weekly: "sum",
		min: 1,
		max: 120,
	},
	strength: {
		label: "Strength",
		unit: "sessions",
		weekly: "sum",
		min: 1,
		max: 3,
	},
	rhr: {
		label: "Resting heart rate",
		unit: "bpm",
		weekly: "latest",
		min: 25,
		max: 140,
	},
	vo2max: {
		label: "VO₂max (measured)",
		unit: "ml/kg/min",
		weekly: "latest",
		min: 10,
		max: 95,
	},
};

export interface Entry {
	id: string;
	day: Day;
	kind: Kind;
	value: number;
}

export interface Profile {
	birthYear: number | null;
	sex: Sex | null;
	maxHr: number | null; // measured; otherwise Tanaka
}

export interface Targets {
	zone2: number;
	zone4: number;
	strength: number;
}

export interface Data {
	version: 1;
	profile: Profile;
	targets: Targets;
	entries: Entry[];
	lastExport: string | null; // ISO time of the last export
}

export const emptyData = (): Data => ({
	version: 1,
	profile: { birthYear: null, sex: null, maxHr: null },
	targets: { ...DEFAULT_TARGETS },
	entries: [],
	lastExport: null,
});

export function validValue(kind: Kind, value: number): boolean {
	const { min, max } = KIND_INFO[kind];
	return Number.isFinite(value) && value >= min && value <= max;
}

export function addEntry(data: Data, entry: Entry): Data {
	if (!validValue(entry.kind, entry.value))
		throw new Error(
			`${KIND_INFO[entry.kind].label} must be ${KIND_INFO[entry.kind].min}-${KIND_INFO[entry.kind].max}`,
		);
	return {
		...data,
		entries: [...data.entries, entry].sort(
			(a, b) => a.day.localeCompare(b.day) || a.id.localeCompare(b.id),
		),
	};
}

export const removeEntry = (data: Data, id: string): Data => ({
	...data,
	entries: data.entries.filter((e) => e.id !== id),
});

export const setProfile = (data: Data, profile: Partial<Profile>): Data => ({
	...data,
	profile: { ...data.profile, ...profile },
});

export const setTargets = (data: Data, targets: Partial<Targets>): Data => ({
	...data,
	targets: { ...data.targets, ...targets },
});

export const exported = (data: Data, at: string): Data => ({
	...data,
	lastExport: at,
});

/** The latest entry of a kind on or before a day. */
export function latest(data: Data, kind: Kind, onOrBefore?: Day): Entry | null {
	for (let i = data.entries.length - 1; i >= 0; i--) {
		const e = data.entries[i] as Entry;
		if (e.kind === kind && (!onOrBefore || e.day <= onOrBefore)) return e;
	}
	return null;
}

export const serialize = (data: Data): string => JSON.stringify(data);

const isNumberOrNull = (v: unknown) =>
	v === null || (typeof v === "number" && Number.isFinite(v));

/** Read stored or imported data; throws with a reason if it isn't SimpleFit data. */
export function parse(json: string): Data {
	let raw: unknown;
	try {
		raw = JSON.parse(json);
	} catch {
		throw new Error("not a JSON file");
	}
	const d = raw as Partial<Data>;
	if (!d || typeof d !== "object" || d.version !== 1)
		throw new Error("not a SimpleFit backup (version 1)");
	const defaults = emptyData();
	const p = { ...defaults.profile, ...(d.profile ?? {}) };
	if (
		!isNumberOrNull(p.birthYear) ||
		!isNumberOrNull(p.maxHr) ||
		![null, "female", "male"].includes(p.sex)
	)
		throw new Error("the profile is malformed");
	const t = { ...defaults.targets, ...(d.targets ?? {}) };
	if (!Object.values(t).every((v) => typeof v === "number" && v >= 0))
		throw new Error("the targets are malformed");
	if (!Array.isArray(d.entries)) throw new Error("the entries are missing");
	const entries = d.entries.filter(
		(e): e is Entry =>
			typeof e?.id === "string" &&
			isDay(e.day) &&
			(KINDS as readonly string[]).includes(e.kind) &&
			validValue(e.kind, e.value),
	);
	if (entries.length !== d.entries.length)
		throw new Error(
			`${d.entries.length - entries.length} entries are malformed`,
		);
	if (
		d.lastExport !== null &&
		d.lastExport !== undefined &&
		typeof d.lastExport !== "string"
	)
		throw new Error("the last export time is malformed");
	return {
		version: 1,
		profile: p,
		targets: t,
		entries,
		lastExport: d.lastExport ?? null,
	};
}
