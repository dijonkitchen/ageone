import { describe, expect, test } from "bun:test";
import {
	allParts,
	DATA,
	LAYERS,
	part,
	relations,
	SEGMENTS,
	STRUCTURES,
	search,
	VIEWS,
} from "./data";
import { drawings, segmentOf } from "./drawings";
import { drawnIds } from "./svg";

const drawnAnywhere = new Set(VIEWS.flatMap((v) => [...drawnIds(v)]));

describe("data file", () => {
	test("ids are FMA ids and unique, across structures and their sides", () => {
		const ids = STRUCTURES.flatMap((s) => [
			s.id,
			...(s.sides ? [s.sides.right, s.sides.left] : []),
		]);
		expect(new Set(ids).size).toBe(ids.length);
		for (const id of ids) expect(id).toMatch(/^FMA:\d+$/);
		expect(allParts().length).toBe(ids.length);
	});

	test("every structure has its names, a description, and a sane count", () => {
		for (const s of STRUCTURES) {
			expect(s.name.length).toBeGreaterThan(1);
			expect(s.latin.length).toBeGreaterThan(1);
			expect(s.description.length).toBeGreaterThan(20);
			expect(s.count).toBeGreaterThanOrEqual(1);
			if (s.sides) expect(s.count % 2).toBe(0);
		}
	});

	test("every relation points to a real structure", () => {
		for (const s of STRUCTURES)
			for (const r of relations(s))
				for (const id of r.ids)
					expect(part(id), `${s.name} → ${id}`).toBeDefined();
	});

	test("bones add up to the 206 of an adult skeleton", () => {
		const bones = STRUCTURES.filter((s) => s.system === "skeleton").reduce(
			(n, s) => n + s.count,
			0,
		);
		expect(bones).toBe(206);
	});

	test("every muscle names the bones it attaches to, its action, and its nerve", () => {
		for (const s of STRUCTURES.filter((x) => x.system === "muscles")) {
			expect(s.origin?.length, s.name).toBeGreaterThan(0);
			expect(s.insertion?.length, s.name).toBeGreaterThan(0);
			for (const id of [...(s.origin ?? []), ...(s.insertion ?? [])])
				expect(part(id)?.structure.system).toBe("skeleton");
			expect(s.action).toBeTruthy();
			expect(s.nerve).toBeTruthy();
		}
	});

	test("each bone's joints and each organ's neighbors are listed", () => {
		for (const s of STRUCTURES) {
			// The hyoid is the one bone that meets no other bone: muscles and ligaments hold it.
			if (s.system === "skeleton" && s.name !== "Hyoid bone")
				expect(s.joints?.length, s.name).toBeGreaterThan(0);
			if (s.system === "organs")
				expect(s.neighbors?.length, s.name).toBeGreaterThan(0);
		}
	});

	test("layers run deep to superficial, skeleton first and skin last", () => {
		expect(LAYERS[0]?.id).toBe("skeleton");
		expect(LAYERS.at(-1)?.id).toBe("skin");
		for (const l of ["skeleton", "muscles", "organs", "skin"])
			expect(LAYERS.find((x) => x.id === l)?.planned).toBeUndefined();
	});

	test("every source has a license and a use", () => {
		for (const s of DATA.sources) {
			expect(s.license).toBeTruthy();
			expect(s.use).toBeTruthy();
		}
	});
});

describe("data and drawings agree", () => {
	test("every drawn id has data, in the layer of its system", () => {
		for (const v of VIEWS)
			for (const d of drawings(v)) {
				if (!d.id) continue;
				const p = part(d.id);
				expect(p, `${v}: ${d.id}`).toBeDefined();
				expect(p?.structure.system).toBe(d.layer);
			}
	});

	test("every data id is drawn somewhere or marked not drawn", () => {
		for (const s of STRUCTURES) {
			const ids = s.sides ? [s.sides.right, s.sides.left] : [s.id];
			if (s.notDrawn) {
				for (const id of ids)
					expect(
						drawnAnywhere.has(id),
						`${s.name} is marked not drawn but is`,
					).toBe(false);
				continue;
			}
			for (const id of ids)
				expect(drawnAnywhere.has(id), `${s.name}: ${id} is not drawn`).toBe(
					true,
				);
		}
	});

	test("paired structures are drawn on both sides in the front and back views", () => {
		for (const v of ["front", "back"] as const) {
			const drawn = drawnIds(v);
			for (const s of STRUCTURES)
				if (s.sides && drawn.has(s.sides.right))
					expect(drawn.has(s.sides.left), `${v}: ${s.name}`).toBe(true);
		}
	});

	test("no shape is drawn twice in one view", () => {
		for (const v of VIEWS) {
			const ids = drawings(v).flatMap((d) => (d.id ? [d.id] : []));
			expect(new Set(ids).size).toBe(ids.length);
		}
	});
});

describe("skeleton segments", () => {
	test("form one tree rooted at the pelvis", () => {
		const ids = new Set(SEGMENTS.map((s) => s.id));
		expect(ids.size).toBe(SEGMENTS.length);
		expect(SEGMENTS.filter((s) => s.parent === null).map((s) => s.id)).toEqual([
			"pelvis",
		]);
		for (const s of SEGMENTS) {
			let at: string | null = s.id;
			const seen = new Set<string>();
			while (at) {
				expect(seen.has(at)).toBe(false);
				seen.add(at);
				at = SEGMENTS.find((x) => x.id === at)?.parent ?? null;
			}
			if (s.parent) expect(ids.has(s.parent)).toBe(true);
		}
	});

	test("cover every drawn bone exactly once", () => {
		const owners = new Map<string, number>();
		for (const s of SEGMENTS)
			for (const b of s.bones) owners.set(b, (owners.get(b) ?? 0) + 1);
		for (const [b, n] of owners) {
			expect(n, b).toBe(1);
			expect(part(b)?.structure.system).toBe("skeleton");
		}
		for (const v of VIEWS)
			for (const d of drawings(v))
				if (d.id && d.layer === "skeleton")
					expect(segmentOf(d.id), d.id).not.toBeNull();
	});

	test("have a joint and ranges of motion that include the rest pose", () => {
		for (const s of SEGMENTS) {
			if (!s.parent) continue;
			expect(s.joint, s.id).toBeTruthy();
			expect(s.motion.length, s.id).toBeGreaterThan(0);
			for (const m of s.motion) {
				expect(m.min).toBeLessThanOrEqual(0);
				expect(m.max).toBeGreaterThanOrEqual(0);
				expect(m.max - m.min).toBeGreaterThan(0);
				expect(m.max - m.min).toBeLessThanOrEqual(360);
				expect(m.negative && m.positive).toBeTruthy();
			}
		}
	});

	test("left and right segments mirror each other", () => {
		for (const s of SEGMENTS.filter((x) => x.id.endsWith("-right"))) {
			const left = SEGMENTS.find(
				(x) => x.id === s.id.replace(/-right$/, "-left"),
			);
			expect(left, s.id).toBeDefined();
			expect(left?.pivot.front).toEqual([-s.pivot.front[0], s.pivot.front[1]]);
			expect(left?.motion.length).toBe(s.motion.length);
		}
	});
});

describe("search", () => {
	const names = (q: string) => search(q).map((s) => s.name);

	test("finds by common name, best match first", () => {
		expect(names("femur")[0]).toBe("Femur");
		expect(names("liver")[0]).toBe("Liver");
	});

	test("finds by synonym and by Latin name", () => {
		expect(names("thigh bone")[0]).toBe("Femur");
		expect(names("innominate")).toContain("Hip bone");
		expect(names("musculus temporalis")[0]).toBe("Temporalis");
	});

	test("ignores case, accents, and punctuation, and returns nothing for nothing", () => {
		expect(names("  FÉMUR! ")[0]).toBe("Femur");
		expect(search("")).toEqual([]);
		expect(search("zzzz")).toEqual([]);
	});

	test("limits the results", () => {
		expect(search("a", 5).length).toBe(5);
	});
});
