import { describe, expect, test } from "bun:test";
import { SEGMENTS, VIEWS } from "./data";
import { drawnIds, elementId, layerMarkup, segmentsIn } from "./svg";

const LAYERS = ["skeleton", "muscles", "organs", "skin"] as const;

/** Each segment group's enclosing segment group, read from the markup. */
function nesting(markup: string): Map<string, string | null> {
	const out = new Map<string, string | null>();
	const stack: (string | null)[] = [];
	for (const [tag] of markup.matchAll(/<\/?g\b[^>]*>/g)) {
		if (tag.startsWith("</")) {
			stack.pop();
			continue;
		}
		const seg = tag.match(/data-segment="([^"]+)"/)?.[1] ?? null;
		if (seg) out.set(seg, [...stack].reverse().find((s) => s !== null) ?? null);
		stack.push(seg);
	}
	return out;
}

describe("SVG markup", () => {
	test("every view and layer renders, with one element per drawn id", () => {
		for (const v of VIEWS) {
			const all = LAYERS.map((l) => layerMarkup(v, l)).join("");
			const ids = [...all.matchAll(/ id="([^"]+)"/g)].map((m) => m[1]);
			expect(new Set(ids).size).toBe(ids.length);
			expect(ids.sort()).toEqual([...drawnIds(v)].map(elementId).sort());
		}
	});

	test("every structure has a text name for screen readers", () => {
		for (const v of VIEWS)
			for (const l of LAYERS)
				for (const [tag] of layerMarkup(v, l).matchAll(
					/<path class="structure"[^>]*>|<path [^>]*class="structure"[^>]*>/g,
				)) {
					expect(tag).toMatch(/aria-label="[^"]{3,}"/);
					expect(tag).toMatch(/role="img"/);
				}
	});

	test("the skeleton nests segment groups as the segment tree", () => {
		for (const v of VIEWS) {
			const shown = segmentsIn(v);
			const tree = nesting(layerMarkup(v, "skeleton"));
			expect([...tree.keys()].sort()).toEqual(shown.map((s) => s.id).sort());
			for (const s of shown)
				expect(tree.get(s.id), `${v}: ${s.id}`).toBe(s.parent);
		}
	});

	test("the side view shows the right side only", () => {
		expect(segmentsIn("side").some((s) => s.id.endsWith("-left"))).toBe(false);
		expect(segmentsIn("front").length).toBe(SEGMENTS.length);
		expect([...drawnIds("side")].length).toBeLessThan(
			[...drawnIds("front")].length,
		);
	});
});
