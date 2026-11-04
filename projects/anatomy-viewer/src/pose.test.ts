import { describe, expect, test } from "bun:test";
import { SEGMENTS } from "./data";
import { rotate } from "./geometry";
import { pose } from "./pose";
import { drawnIds, layerMarkup, restPivot } from "./svg";

const seg = (id: string) => {
	const s = SEGMENTS.find((x) => x.id === id);
	if (!s) throw new Error(id);
	return s;
};
const close = (a: number[] | undefined, b: number[]) => {
	expect(a).toBeDefined();
	for (const [i, v] of b.entries()) expect(a?.[i]).toBeCloseTo(v, 6);
};

describe("posing the skeleton", () => {
	test("at rest, every pivot stays where the data puts it", () => {
		for (const view of ["front", "back", "side"] as const)
			for (const [id, p] of pose(view))
				close(p.pivot, restPivot(seg(id), view));
	});

	test("flexing the right elbow carries the hand with the forearm", () => {
		const elbow = restPivot(seg("forearm-right"), "side");
		const wrist = restPivot(seg("hand-right"), "side");
		const posed = pose("side", { "forearm-right": -90 });
		close(posed.get("forearm-right")?.pivot, elbow);
		close(posed.get("hand-right")?.pivot, rotate(wrist, -90, elbow));
		close(
			posed.get("upper-arm-right")?.pivot,
			restPivot(seg("upper-arm-right"), "side"),
		);
	});

	test("turns compose down the chain, and only below the turned joint", () => {
		const shoulder = restPivot(seg("upper-arm-right"), "front");
		const elbow = restPivot(seg("forearm-right"), "front");
		const wrist = restPivot(seg("hand-right"), "front");
		const posed = pose("front", { "upper-arm-right": 30, "forearm-right": 20 });
		const elbowNow = rotate(elbow, 30, shoulder);
		close(posed.get("forearm-right")?.pivot, elbowNow);
		close(
			posed.get("hand-right")?.pivot,
			rotate(rotate(wrist, 30, shoulder), 20, elbowNow),
		);
		for (const id of ["hand-left", "foot-right", "head"])
			close(posed.get(id)?.pivot, restPivot(seg(id), "front"));
	});

	test("a turned segment still draws every structure, rotated about its joint", () => {
		const range = seg("forearm-right").motion.find((m) => m.view === "side");
		expect(range).toBeDefined();
		const angle = range?.min ?? 0;
		const markup = layerMarkup("side", "skeleton", { "forearm-right": angle });
		const [x, y] = restPivot(seg("forearm-right"), "side");
		expect(markup).toContain(
			`data-segment="forearm-right" data-pivot="${x} ${y}" transform="rotate(${angle} ${x} ${y})"`,
		);
		const ids = [...markup.matchAll(/data-id="([^"]+)"/g)].map((m) => m[1]);
		const skeleton = [...drawnIds("side")].filter((id) =>
			layerMarkup("side", "skeleton").includes(`data-id="${id}"`),
		);
		expect(ids.sort()).toEqual(skeleton.sort());
	});
});
