import { expect, test } from "bun:test";
import { BASE } from "./generate";
import {
	analyse,
	canonical,
	catalog,
	edgeAt,
	features,
	formatCode,
	parseCode,
	rotatePoint,
	rotatePort,
} from "./tiles";

test("codes round-trip and reject bad input", () => {
	for (const code of ["CRFR", "FRRR+J", "CCFF+S", "CRCR+S+D", "FFRF+M"])
		expect(formatCode(parseCode(code))).toBe(code);
	expect(() => parseCode("CRF")).toThrow();
	expect(() => parseCode("CRFQ")).toThrow();
	expect(() => parseCode("CRFR+Q")).toThrow();
	expect(() => parseCode("CCFF+S+S")).toThrow();
});

test("every base kind is a valid layout", () => {
	for (const code of Object.keys(BASE))
		expect(analyse(code)).not.toBeTypeOf("string");
});

test("layouts that break the rules are rejected", () => {
	expect(analyse("FFFR")).toBe(
		"a road that ends needs a city, monastery, or junction to end at",
	);
	expect(analyse("FRRR")).toBe("three or four roads need a junction (+J)");
	expect(analyse("CFFF+M")).toBe("a monastery tile has no city");
	expect(analyse("CFFF+S")).toBe("+S needs one city of two or more edges");
	expect(analyse("CFFF+X")).toBe("+X needs two or more city edges");
	expect(analyse("RFRF+J")).toBe("+J needs three or four roads");
});

test("every catalog tile is valid and listed once, in its smallest rotation", () => {
	const all = catalog();
	expect(all.length).toBeGreaterThan(30);
	expect(new Set(all).size).toBe(all.length);
	for (const code of all) {
		expect(canonical(code)).toBe(code);
		expect(analyse(code)).not.toBeTypeOf("string");
	}
	for (const code of Object.keys(BASE)) expect(all).toContain(canonical(code));
});

test("fields are split by roads and cities and know which cities they touch", () => {
	// City on top, road across: a field between city and road, and one below the road.
	const f = features("CRFR");
	expect(f.cities).toHaveLength(1);
	expect(f.roads).toEqual([expect.objectContaining({ sides: [1, 3] })]);
	expect(f.fields.map((x) => x.ports)).toEqual([
		[3, 11],
		[5, 6, 7, 8, 9],
	]);
	expect(f.fields.map((x) => x.cities)).toEqual([[0], []]);
	// Two caps that are separate cities, both touching the one field.
	const x = features("CCFF+X");
	expect(x.cities).toHaveLength(2);
	expect(x.fields).toEqual([expect.objectContaining({ cities: [0, 1] })]);
	// A four-way junction ends four roads and makes four fields.
	expect(features("RRRR+J").fields).toHaveLength(4);
	expect(features("FFFF+M").monastery).not.toBeNull();
});

test("rotation moves edges, points, and ports clockwise", () => {
	expect(
		[0, 1, 2, 3].map((s) => edgeAt("CRFF", 1, s as 0 | 1 | 2 | 3)).join(""),
	).toBe("FCRF");
	expect(rotatePoint([0.5, 0], 1)).toEqual([1, 0.5]);
	expect(rotatePoint([0.5, 0], 4)).toEqual([0.5, 0]);
	expect(rotatePort(0, 1)).toBe(3);
	expect(rotatePort(11, 1)).toBe(2);
	expect(canonical("RFRF")).toBe("FRFR");
});
