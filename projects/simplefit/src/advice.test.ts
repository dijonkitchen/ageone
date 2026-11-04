import { expect, test } from "bun:test";
import { backupDue, heart, nextAction, trends, vo2max, week } from "./advice";
import { addDays } from "./dates";
import {
	addEntry,
	type Data,
	type Entry,
	emptyData,
	exported,
	setProfile,
} from "./store";

const TODAY = "2026-10-23"; // a Friday; the week started Monday the 19th
let n = 0;
const log = (d: Data, day: string, kind: Entry["kind"], value: number) =>
	addEntry(d, { id: String(n++), day, kind, value });
const person = () => setProfile(emptyData(), { birthYear: 1986, sex: "male" });

test("zones come from Tanaka's max and the latest resting heart rate, or a measured max", () => {
	let d = log(person(), "2026-10-20", "rhr", 60);
	expect(heart(d, TODAY)).toMatchObject({
		max: 180,
		rest: 60,
		zone2: [132, 144],
		zone4: [156, 168],
	});
	d = setProfile(d, { maxHr: 190 });
	expect(heart(d, TODAY)).toMatchObject({ max: 190, measuredMax: true });
});

test("VO2max is measured if logged, else estimated, with its band", () => {
	let d = log(person(), "2026-10-20", "rhr", 60);
	expect(vo2max(d, TODAY)).toEqual({
		value: 45.9,
		measured: false,
		band: "high", // 40-49: 45.2 is the 80th percentile
	});
	d = log(d, "2026-10-21", "vo2max", 36);
	expect(vo2max(d, TODAY)).toEqual({
		value: 36,
		measured: true,
		band: "average",
	});
	expect(vo2max(emptyData(), TODAY)).toBeNull();
});

test("the week sums this week's logs only", () => {
	let d = log(person(), "2026-10-18", "zone2", 60); // last Sunday
	d = log(d, "2026-10-19", "zone2", 30);
	d = log(d, "2026-10-22", "zone2", 45);
	d = log(d, "2026-10-22", "strength", 1);
	expect(week(d, TODAY)).toEqual({ zone2: 75, zone4: 0, strength: 1 });
});

test("the next action asks for the profile, then a resting heart rate, then the biggest gap", () => {
	expect(nextAction(emptyData(), TODAY).kind).toBe("profile");
	let d = person();
	expect(nextAction(d, TODAY).kind).toBe("rhr");
	d = log(d, "2026-10-14", "rhr", 60);
	expect(nextAction(d, TODAY).kind).toBe("rhr"); // more than a week old
	d = log(d, "2026-10-22", "rhr", 60);
	const intervals = nextAction(d, TODAY);
	expect(intervals.kind).toBe("zone4");
	expect(intervals.text).toContain("156-168 bpm");
	d = log(d, "2026-10-20", "zone4", 16);
	expect(nextAction(d, TODAY).kind).toBe("strength");
	d = log(log(d, "2026-10-20", "strength", 1), "2026-10-21", "strength", 1);
	const easy = nextAction(d, TODAY);
	expect(easy.kind).toBe("zone2");
	expect(easy.text).toContain("Do 50 minutes"); // 150 left over 3 days
	d = log(d, "2026-10-21", "zone2", 150);
	expect(nextAction(d, TODAY).kind).toBe("rest");
});

test("trends compare the second half of finished weeks with the first; lower resting heart rate is better", () => {
	let d = person();
	for (let w = 0; w < 8; w++) {
		const day = addDays("2026-08-31", w * 7); // Mondays, the last one this week
		d = log(d, day, "zone2", 60 + w * 10);
		d = log(d, day, "rhr", 64 - w);
		d = log(d, day, "strength", 2);
	}
	const t = Object.fromEntries(trends(d, TODAY).map((x) => [x.kind, x]));
	expect(t.zone2?.points).toEqual([60, 70, 80, 90, 100, 110, 120, 130]);
	expect(t.zone2?.direction).toBe("improving");
	expect(t.rhr?.direction).toBe("improving");
	expect(t.strength?.direction).toBe("steady");
	expect(t.vo2max?.direction).toBe("not enough data");
	expect(Number.isNaN(t.vo2max?.points[0])).toBe(true);
	// Logging only this week says nothing yet.
	const fresh = trends(log(person(), "2026-10-20", "zone2", 45), TODAY);
	expect(fresh.find((x) => x.kind === "zone2")?.direction).toBe(
		"not enough data",
	);
});

test("the backup reminder shows with no export or one over 30 days old, and clears after an export", () => {
	const now = new Date("2026-10-23T12:00:00Z");
	expect(backupDue(emptyData(), now)).toBe(false); // nothing to back up
	let d = log(person(), "2026-10-20", "rhr", 60);
	expect(backupDue(d, now)).toBe(true);
	d = exported(d, "2026-09-20T12:00:00Z");
	expect(backupDue(d, now)).toBe(true);
	d = exported(d, now.toISOString());
	expect(backupDue(d, now)).toBe(false);
	expect(backupDue(d, new Date("2026-11-21T12:00:00Z"))).toBe(false);
	expect(backupDue(d, new Date("2026-11-23T12:00:00Z"))).toBe(true);
});
