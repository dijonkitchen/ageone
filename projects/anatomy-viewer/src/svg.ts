// Turn the drawings into SVG markup, one layer at a time. The skeleton is nested by segment, each group
// carrying its joint's pivot, so turning one segment carries its children (forearm, then hand) with it.
import { label, part, SEGMENTS, type Segment, type View } from "./data";
import { behindParent, type Drawn, drawings, segmentOf } from "./drawings";
import { mirrorPoint, type Point } from "./geometry";

export const VIEWBOX: Record<
	View,
	{ x: number; y: number; w: number; h: number }
> = {
	front: { x: -36, y: -3, w: 72, h: 182 },
	back: { x: -36, y: -3, w: 72, h: 182 },
	side: { x: -36, y: -3, w: 72, h: 182 },
};

export const elementId = (id: string) => id.replace(":", "").toLowerCase();

const esc = (t: string) =>
	t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");

function shape(item: Drawn): string {
	if (!item.id) return `<path class="decor" aria-hidden="true" d="${item.d}"/>`;
	const p = part(item.id);
	if (!p) throw new Error(`drawn id ${item.id} has no data`);
	const rule = item.evenOdd ? ' fill-rule="evenodd"' : "";
	return `<path id="${elementId(item.id)}" class="structure" data-id="${item.id}" data-system="${p.structure.system}" tabindex="-1" role="img" aria-label="${esc(label(p))}"${rule} d="${item.d}"/>`;
}

/** Segments shown in a view: the side view shows only the right side. */
export function segmentsIn(view: View): Segment[] {
	return SEGMENTS.filter((s) => view !== "side" || !s.id.endsWith("-left"));
}

/** A segment's pivot in a view, before any turning. */
export function restPivot(s: Segment, view: View): Point {
	if (view === "side") return s.pivot.side;
	return view === "back" ? mirrorPoint(s.pivot.front) : s.pivot.front;
}

/** Markup for one layer of a view; `angles` turns skeleton segments (degrees, SVG sense) about their pivots. */
export function layerMarkup(
	view: View,
	layer: Drawn["layer"],
	angles: Record<string, number> = {},
): string {
	const items = drawings(view).filter((d) => d.layer === layer);
	if (layer !== "skeleton") return items.map(shape).join("");
	const shown = segmentsIn(view);
	const own = new Map<string, Drawn[]>(shown.map((s) => [s.id, []]));
	let lastSegment: string | null = null;
	for (const item of items) {
		// Decorations belong to the segment of the bone drawn just before them (the skull's eye sockets).
		const seg: string | null = item.id ? segmentOf(item.id) : lastSegment;
		if (!seg || !own.has(seg))
			throw new Error(`no segment in the ${view} view for ${item.id}`);
		own.get(seg)?.push(item);
		lastSegment = seg;
	}
	const children = (id: string | null) => shown.filter((s) => s.parent === id);
	const group = (s: Segment): string => {
		const [px, py] = restPivot(s, view);
		const a = angles[s.id] ?? 0;
		const behind = children(s.id).filter((c) => behindParent(c.id, view));
		const front = children(s.id).filter((c) => !behindParent(c.id, view));
		const transform = a ? ` transform="rotate(${a} ${px} ${py})"` : "";
		return `<g class="segment" data-segment="${s.id}" data-pivot="${px} ${py}"${transform}>${behind.map(group).join("")}${(own.get(s.id) ?? []).map(shape).join("")}${front.map(group).join("")}</g>`;
	};
	return children(null).map(group).join("");
}

/** The structure ids drawn in a view (each paired side separately). */
export function drawnIds(view: View): Set<string> {
	return new Set(drawings(view).flatMap((d) => (d.id ? [d.id] : [])));
}
