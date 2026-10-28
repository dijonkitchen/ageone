// What the numbers mean: this week's progress, the one thing to do next, whether each metric is improving, and
// when to back up. Pure functions of the data and today's date.

import { addDays, type Day, daysBetween, parseDay, weekStart } from "./dates";
import {
	type Band,
	fitnessBand,
	maxHeartRate,
	uthVo2max,
	type Zone,
	zoneRange,
} from "./formulas";
import { type Data, type Entry, KIND_INFO, type Kind, latest } from "./store";

export const BACKUP_DAYS = 30;

export const age = (data: Data, today: Day): number | null =>
	data.profile.birthYear === null
		? null
		: parseDay(today).getFullYear() - data.profile.birthYear;

/** Heart rate numbers: max (measured, else Tanaka), resting (latest log), and the zones they give. */
export function heart(data: Data, today: Day) {
	const a = age(data, today);
	const max =
		data.profile.maxHr ?? (a === null ? null : Math.round(maxHeartRate(a)));
	const rest = latest(data, "rhr", today)?.value ?? null;
	const zone = (z: Zone) =>
		max !== null && rest !== null ? zoneRange(z, rest, max) : null;
	return {
		max,
		measuredMax: data.profile.maxHr !== null,
		rest,
		zone2: zone(2),
		zone4: zone(4),
	};
}

/** VO2max: the latest measured value, else Uth's estimate, with its FRIEND band when age and sex are known. */
export function vo2max(
	data: Data,
	today: Day,
): { value: number; measured: boolean; band: Band | null } | null {
	const measured = latest(data, "vo2max", today);
	const h = heart(data, today);
	const value =
		measured?.value ??
		(h.max !== null && h.rest !== null ? uthVo2max(h.max, h.rest) : null);
	if (value === null) return null;
	const a = age(data, today);
	const band =
		a !== null && data.profile.sex
			? fitnessBand(value, a, data.profile.sex)
			: null;
	return {
		value: Math.round(value * 10) / 10,
		measured: measured !== null,
		band,
	};
}

const inWeek = (e: Entry, start: Day) =>
	e.day >= start && e.day < addDays(start, 7);

/** Totals for the week holding `day`. */
export function week(
	data: Data,
	day: Day,
): Record<"zone2" | "zone4" | "strength", number> {
	const start = weekStart(day);
	const sum = (kind: Kind) =>
		data.entries
			.filter((e) => e.kind === kind && inWeek(e, start))
			.reduce((s, e) => s + e.value, 0);
	return {
		zone2: sum("zone2"),
		zone4: sum("zone4"),
		strength: sum("strength"),
	};
}

export interface Action {
	kind: Kind | "profile" | "backup" | "rest";
	text: string;
}

/** The single most useful thing to do next. */
export function nextAction(data: Data, today: Day): Action {
	const h = heart(data, today);
	if (data.profile.birthYear === null)
		return {
			kind: "profile",
			text: "Add your birth year so SimpleFit can work out your heart rate zones.",
		};
	const lastRhr = latest(data, "rhr", today);
	if (!lastRhr || daysBetween(lastRhr.day, today) >= 7)
		return {
			kind: "rhr",
			text: "Log your resting heart rate: measure it lying down, first thing in the morning.",
		};
	const done = week(data, today);
	const t = data.targets;
	const daysLeft = 7 - daysBetween(weekStart(today), today);
	const range = (r: [number, number] | null) =>
		r ? ` at ${r[0]}-${r[1]} bpm` : "";
	if (done.zone4 < t.zone4)
		return {
			kind: "zone4",
			text: `Do an interval session: 4 x 4 minutes${range(h.zone4)}, 3 minutes easy between (${t.zone4 - done.zone4} min to go this week).`,
		};
	if (done.strength < t.strength)
		return {
			kind: "strength",
			text: `Do a strength session working all major muscle groups (${t.strength - done.strength} to go this week).`,
		};
	if (done.zone2 < t.zone2) {
		const left = t.zone2 - done.zone2;
		const perDay = Math.ceil(left / daysLeft);
		return {
			kind: "zone2",
			text: `Do ${Math.min(left, Math.max(30, perDay))} minutes of Zone 2${range(h.zone2)}: you can still talk in full sentences (${left} min to go this week).`,
		};
	}
	return {
		kind: "rest",
		text: "Every target is met this week. Rest, or keep anything else easy.",
	};
}

export type Direction =
	| "improving"
	| "worsening"
	| "steady"
	| "not enough data";

export interface Trend {
	kind: Kind;
	points: number[]; // weekly totals (or weekly latest values), oldest first
	direction: Direction;
}

/** Weekly series over `weeks` weeks ending this week, and whether the last half beats the first. */
export function trends(data: Data, today: Day, weeks = 8): Trend[] {
	const starts = Array.from({ length: weeks }, (_, i) =>
		addDays(weekStart(today), -7 * (weeks - 1 - i)),
	);
	return (Object.keys(KIND_INFO) as Kind[]).map((kind) => {
		const info = KIND_INFO[kind];
		const points = starts.map((start) => {
			const these = data.entries.filter(
				(e) => e.kind === kind && inWeek(e, start),
			);
			if (info.weekly === "sum") return these.reduce((s, e) => s + e.value, 0);
			return these.length
				? these.reduce((s, e) => s + e.value, 0) / these.length
				: Number.NaN;
		});
		// This week is still in progress, so sums compare finished weeks only.
		const done = info.weekly === "sum" ? points.slice(0, -1) : points;
		const half = Math.floor(done.length / 2);
		const mean = (xs: number[]) => {
			const real = xs.filter((x) => !Number.isNaN(x));
			return real.length ? real.reduce((s, x) => s + x, 0) / real.length : null;
		};
		const before = mean(done.slice(0, half));
		const after = mean(done.slice(half));
		let direction: Direction = "not enough data";
		// A direction needs logs from the first half of the window on.
		const first = data.entries.find((e) => e.kind === kind)?.day;
		const early = first !== undefined && first < (starts[half] as Day);
		if (early && before !== null && after !== null) {
			const change = (after - before) / Math.max(1e-9, Math.abs(before));
			const better = kind === "rhr" ? -change : change;
			direction =
				Math.abs(change) < 0.03
					? "steady"
					: better > 0
						? "improving"
						: "worsening";
		}
		return { kind, points, direction };
	});
}

/** Whether to remind about a backup: there is data, and no export in the last BACKUP_DAYS days. */
export function backupDue(data: Data, now: Date): boolean {
	if (!data.entries.length) return false;
	if (!data.lastExport) return true;
	return (
		(now.getTime() - new Date(data.lastExport).getTime()) / 86_400_000 >
		BACKUP_DAYS
	);
}
