// The fitness formulas, as pure functions with their sources. Every number here is cited; see the tests.

export type Sex = "female" | "male";

/**
 * Age-predicted maximal heart rate: 208 - 0.7 x age (beats per minute).
 * Tanaka H, Monahan KD, Seals DR. Age-predicted maximal heart rate revisited.
 * J Am Coll Cardiol. 2001;37(1):153-156. doi:10.1016/S0735-1097(00)01054-8. The same for men and women; SEE about 10 bpm.
 */
export const maxHeartRate = (age: number): number => 208 - 0.7 * age;

/**
 * Karvonen (heart rate reserve) target: rest + intensity x (max - rest).
 * Karvonen MJ, Kentala E, Mustala O. The effects of training on heart rate; a longitudinal study.
 * Ann Med Exp Biol Fenn. 1957;35(3):307-315.
 */
export const karvonen = (
	rest: number,
	max: number,
	intensity: number,
): number => rest + intensity * (max - rest);

/**
 * The five training zones as fractions of heart rate reserve, used with `karvonen`. The 10-point bands are the
 * common convention, not part of Karvonen's paper: zone 2 is easy aerobic work, zone 4 is hard intervals.
 */
export const ZONES = {
	1: [0.5, 0.6],
	2: [0.6, 0.7],
	3: [0.7, 0.8],
	4: [0.8, 0.9],
	5: [0.9, 1],
} as const;
export type Zone = keyof typeof ZONES;

/** A zone's heart rate range in whole beats per minute. */
export function zoneRange(
	zone: Zone,
	rest: number,
	max: number,
): [number, number] {
	const [low, high] = ZONES[zone];
	return [
		Math.round(karvonen(rest, max, low)),
		Math.round(karvonen(rest, max, high)),
	];
}

/**
 * VO2max estimate from the heart rate ratio: 15.3 x HRmax / HRrest (ml/kg/min).
 * Uth N, Sorensen H, Overgaard K, Pedersen PK. Estimation of VO2max from the ratio between HRmax and HRrest -
 * the Heart Rate Ratio Method. Eur J Appl Physiol. 2004;91(1):111-115. doi:10.1007/s00421-003-0988-y.
 * Derived in well-trained men; a measured VO2max always overrides it.
 */
export const uthVo2max = (max: number, rest: number): number =>
	(15.3 * max) / rest;

/**
 * Treadmill VO2peak percentiles (ml/kg/min) by sex and age decade, 20-29 to 80-89, for the 10th to 90th percentiles.
 * Kaminsky LA, Arena R, Myers J, et al. Updated Reference Standards for Cardiorespiratory Fitness Measured with
 * Cardiopulmonary Exercise Testing: Data from the Fitness Registry and the Importance of Exercise National Database
 * (FRIEND). Mayo Clin Proc. 2022;97(2):285-293. doi:10.1016/j.mayocp.2021.08.020.
 */
export const FRIEND_PERCENTILES = [10, 20, 30, 40, 50, 60, 70, 80, 90] as const;
export const FRIEND: Record<Sex, readonly (readonly number[])[]> = {
	// One row per decade (20-29 first); one column per percentile in FRIEND_PERCENTILES.
	male: [
		[28.6, 35.2, 40.0, 43.6, 46.5, 49.0, 51.9, 54.5, 58.6],
		[24.9, 29.8, 33.5, 37.0, 39.7, 43.4, 46.4, 50.0, 55.5],
		[22.1, 26.7, 29.7, 32.4, 35.3, 37.9, 40.9, 45.2, 50.8],
		[18.6, 22.2, 24.5, 26.9, 29.2, 31.8, 34.3, 38.3, 43.4],
		[15.8, 18.5, 20.7, 22.8, 24.6, 26.5, 28.7, 32.0, 37.1],
		[13.6, 15.9, 17.3, 19.1, 20.6, 22.2, 23.8, 25.9, 29.4],
		[12.9, 14.8, 16.1, 16.6, 17.6, 18.4, 20.0, 21.4, 22.8],
	],
	female: [
		[22.5, 27.2, 30.8, 34.0, 36.6, 39.0, 41.8, 44.8, 49.0],
		[18.6, 21.9, 24.2, 26.4, 28.3, 31.0, 33.6, 37.0, 42.1],
		[17.2, 19.7, 21.8, 23.9, 25.7, 27.7, 30.0, 33.0, 37.8],
		[16.5, 18.5, 20.1, 21.5, 22.9, 24.6, 26.3, 28.4, 32.4],
		[13.4, 15.4, 17.0, 18.3, 19.6, 20.9, 22.4, 24.3, 27.3],
		[12.3, 14.0, 15.2, 16.2, 17.2, 18.3, 19.6, 20.8, 22.8],
		[11.4, 12.6, 13.7, 14.7, 15.4, 16.0, 17.3, 18.4, 20.8],
	],
};

export type Band =
	| "low"
	| "below average"
	| "average"
	| "above average"
	| "high"
	| "elite";

/** The approximate percentile of a VO2max for age and sex (under 10 is 0, over 90 is 100), by straight lines between table points. */
export function vo2maxPercentile(
	vo2max: number,
	age: number,
	sex: Sex,
): number {
	const rows = FRIEND[sex];
	const row = rows[
		Math.min(rows.length - 1, Math.max(0, Math.floor((age - 20) / 10)))
	] as readonly number[];
	if (vo2max < (row[0] as number)) return 0;
	for (let i = 1; i < row.length; i++) {
		const lo = row[i - 1] as number;
		const hi = row[i] as number;
		if (vo2max < hi) {
			const p0 = FRIEND_PERCENTILES[i - 1] as number;
			return p0 + ((vo2max - lo) / (hi - lo)) * 10;
		}
	}
	return 100;
}

/** Fitness band from the FRIEND percentile: <20 low, 20-40 below average, 40-60 average, 60-80 above, 80-90 high, 90+ elite. */
export function fitnessBand(vo2max: number, age: number, sex: Sex): Band {
	const p = vo2maxPercentile(vo2max, age, sex);
	if (p < 20) return "low";
	if (p < 40) return "below average";
	if (p < 60) return "average";
	if (p < 80) return "above average";
	if (p < 90) return "high";
	return "elite";
}

/**
 * Default weekly targets. Zone 2: 150 minutes, the low end of WHO's 150-300 minutes of moderate activity; strength:
 * 2 sessions, WHO's "2 or more days a week". Bull FC, Al-Ansari SS, Biddle S, et al. World Health Organization
 * 2020 guidelines on physical activity and sedentary behaviour. Br J Sports Med. 2020;54(24):1451-1462.
 * doi:10.1136/bjsports-2020-102955.
 * Zone 4: 16 minutes, one session of 4 x 4 minutes. Helgerud J, Hoydal K, Wang E, et al. Aerobic high-intensity
 * intervals improve VO2max more than moderate training. Med Sci Sports Exerc. 2007;39(4):665-671. doi:10.1249/mss.0b013e3180304570.
 */
export const DEFAULT_TARGETS = { zone2: 150, zone4: 16, strength: 2 } as const;
