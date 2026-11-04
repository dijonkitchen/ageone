// Each formula is checked against its source's own numbers.
import { expect, test } from "bun:test";
import {
	DEFAULT_TARGETS,
	FRIEND,
	fitnessBand,
	karvonen,
	maxHeartRate,
	uthVo2max,
	vo2maxPercentile,
	zoneRange,
} from "./formulas";

test("Tanaka 2001 (J Am Coll Cardiol 37:153): HRmax = 208 - 0.7 x age, the same for men and women", () => {
	expect(maxHeartRate(20)).toBe(194);
	expect(maxHeartRate(40)).toBe(180);
	expect(maxHeartRate(60)).toBeCloseTo(166);
	// The paper's point: 220 - age underestimates HRmax in older adults.
	expect(maxHeartRate(70)).toBeGreaterThan(220 - 70);
	expect(maxHeartRate(20)).toBeLessThan(220 - 20);
});

test("Karvonen 1957 (Ann Med Exp Biol Fenn 35:307): target = rest + intensity x (max - rest)", () => {
	expect(karvonen(60, 180, 0)).toBe(60);
	expect(karvonen(60, 180, 1)).toBe(180);
	expect(karvonen(60, 180, 0.6)).toBe(132);
	expect(zoneRange(2, 60, 180)).toEqual([132, 144]);
	expect(zoneRange(4, 60, 180)).toEqual([156, 168]);
});

test("Uth 2004 (Eur J Appl Physiol 91:111): VO2max = 15.3 x HRmax / HRrest", () => {
	expect(uthVo2max(200, 50)).toBeCloseTo(61.2);
	expect(uthVo2max(180, 60)).toBeCloseTo(45.9);
});

test("FRIEND 2022 (Mayo Clin Proc 97:285): treadmill percentiles rise with percentile and fall with age", () => {
	// Medians from the paper's treadmill table: men 20-29 46.5, women 20-29 36.6.
	expect(FRIEND.male[0]?.[4]).toBe(46.5);
	expect(FRIEND.female[0]?.[4]).toBe(36.6);
	for (const sex of ["male", "female"] as const)
		for (const [i, row] of FRIEND[sex].entries()) {
			expect(row).toHaveLength(9);
			for (let j = 1; j < row.length; j++)
				expect(row[j]).toBeGreaterThan(row[j - 1] as number);
			const older = FRIEND[sex][i + 1];
			if (older) expect(older[4]).toBeLessThan(row[4] as number);
		}
	expect(vo2maxPercentile(46.5, 25, "male")).toBe(50);
	expect(vo2maxPercentile(47.75, 25, "male")).toBeCloseTo(55);
	expect(vo2maxPercentile(10, 25, "male")).toBe(0);
	expect(vo2maxPercentile(70, 25, "male")).toBe(100);
	// Ages outside 20-89 use the nearest decade.
	expect(vo2maxPercentile(46.5, 18, "male")).toBe(50);
	expect(vo2maxPercentile(17.6, 95, "male")).toBe(50);
	expect(fitnessBand(36.6, 25, "female")).toBe("average");
	expect(fitnessBand(36.6, 45, "female")).toBe("high");
	expect(fitnessBand(20, 25, "female")).toBe("low");
	expect(fitnessBand(60, 25, "male")).toBe("elite");
});

test("default targets: WHO 2020 (150 min, strength 2 days) and Helgerud 2007 (4 x 4 min)", () => {
	expect(DEFAULT_TARGETS).toEqual({ zone2: 150, zone4: 16, strength: 2 });
});
