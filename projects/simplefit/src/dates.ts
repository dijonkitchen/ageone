// Local calendar dates as "YYYY-MM-DD" strings, and weeks that start on Monday (ISO 8601).

export type Day = string;

const pad = (n: number) => String(n).padStart(2, "0");

export const dayOf = (d: Date): Day =>
	`${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

/** Parse a day at local noon, so adding days never trips over a daylight saving change. */
export function parseDay(day: Day): Date {
	const [y, m, d] = day.split("-").map(Number);
	return new Date(y ?? 1970, (m ?? 1) - 1, d ?? 1, 12);
}

export function addDays(day: Day, n: number): Day {
	const d = parseDay(day);
	d.setDate(d.getDate() + n);
	return dayOf(d);
}

/** The Monday of the day's week. */
export function weekStart(day: Day): Day {
	const d = parseDay(day);
	return addDays(day, -((d.getDay() + 6) % 7));
}

export const daysBetween = (a: Day, b: Day): number =>
	Math.round((parseDay(b).getTime() - parseDay(a).getTime()) / 86_400_000);

export const isDay = (s: unknown): s is Day =>
	typeof s === "string" &&
	/^\d{4}-\d{2}-\d{2}$/.test(s) &&
	dayOf(parseDay(s)) === s;
