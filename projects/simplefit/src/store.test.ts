import { expect, test } from "bun:test";
import { addDays, daysBetween, isDay, weekStart } from "./dates";
import {
	addEntry,
	emptyData,
	exported,
	latest,
	parse,
	removeEntry,
	serialize,
	setProfile,
	setTargets,
} from "./store";

test("weeks start on Monday and days survive daylight saving changes", () => {
	expect(weekStart("2026-10-23")).toBe("2026-10-19"); // a Friday
	expect(weekStart("2026-10-19")).toBe("2026-10-19");
	expect(weekStart("2026-10-25")).toBe("2026-10-19"); // Sunday
	expect(addDays("2026-03-07", 2)).toBe("2026-03-09");
	expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
	expect(daysBetween("2026-10-01", "2026-11-01")).toBe(31);
	expect(isDay("2026-02-30")).toBe(false);
	expect(isDay("2026-02-28")).toBe(true);
});

test("entries are validated, kept in day order, and removable", () => {
	let d = addEntry(emptyData(), {
		id: "b",
		day: "2026-10-20",
		kind: "zone2",
		value: 40,
	});
	d = addEntry(d, { id: "a", day: "2026-10-19", kind: "rhr", value: 58 });
	expect(d.entries.map((e) => e.id)).toEqual(["a", "b"]);
	expect(() =>
		addEntry(d, { id: "c", day: "2026-10-20", kind: "rhr", value: 300 }),
	).toThrow("Resting heart rate");
	expect(() =>
		addEntry(d, {
			id: "c",
			day: "2026-10-20",
			kind: "zone2",
			value: Number.NaN,
		}),
	).toThrow();
	expect(latest(d, "rhr")?.value).toBe(58);
	expect(latest(d, "rhr", "2026-10-18")).toBeNull();
	expect(removeEntry(d, "a").entries).toHaveLength(1);
});

test("a backup restores everything, and anything else is refused with a reason", () => {
	let d = addEntry(emptyData(), {
		id: "a",
		day: "2026-10-19",
		kind: "vo2max",
		value: 44,
	});
	d = setProfile(d, { birthYear: 1985, sex: "female", maxHr: 186 });
	d = setTargets(d, { zone2: 180 });
	d = exported(d, "2026-10-23T10:00:00.000Z");
	expect(parse(serialize(d))).toEqual(d);
	expect(parse(JSON.stringify(d, null, 2))).toEqual(d);
	expect(() => parse("{oops")).toThrow("not a JSON file");
	expect(() => parse('{"version":2}')).toThrow("not a SimpleFit backup");
	expect(() =>
		parse(
			JSON.stringify({
				...d,
				entries: [{ id: "x", day: "2026-13-01", kind: "zone2", value: 5 }],
			}),
		),
	).toThrow("1 entries are malformed");
	expect(() =>
		parse(JSON.stringify({ ...d, profile: { sex: "other" } })),
	).toThrow("profile");
	// Older backups without newer fields get the defaults.
	expect(parse('{"version":1,"entries":[]}')).toEqual(emptyData());
});
