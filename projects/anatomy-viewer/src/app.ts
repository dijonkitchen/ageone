// The page: draws the chosen view layer by layer (each built only when first shown), shows details on
// hover and pick, searches by name, and zooms and pans with mouse, touch, and keyboard.
import {
	DATA,
	LAYERS,
	label,
	part,
	relations,
	type Side,
	type Structure,
	SYSTEM_NAMES,
	search,
	VIEWS,
	type View,
} from "./data";
import { type Drawn, segmentOf } from "./drawings";
import { drawnIds, elementId, layerMarkup, VIEWBOX } from "./svg";

type LayerState = "shown" | "faded" | "hidden";
type DrawnLayer = Drawn["layer"];
const DRAWN: DrawnLayer[] = ["skeleton", "muscles", "organs", "skin"];
const CHOICES: [LayerState, string][] = [
	["shown", "Show"],
	["faded", "Fade"],
	["hidden", "Hide"],
];
const VIEW_NAMES: Record<View, string> = {
	front: "front",
	back: "back",
	side: "right side",
};

const $ = <T extends Element>(sel: string) => document.querySelector(sel) as T;
const stage = $<SVGSVGElement>("#stage");
const wrap = $<HTMLElement>(".stage-wrap");
const tip = $<HTMLElement>("#tip");
const details = $<HTMLElement>("#details");
const q = $<HTMLInputElement>("#q");
const results = $<HTMLElement>("#results");

const state = {
	view: "front" as View,
	layers: {
		skeleton: "shown",
		muscles: "shown",
		organs: "hidden",
		skin: "hidden",
	} as Record<DrawnLayer, LayerState>,
	picked: null as string | null,
	hovered: null as string | null,
	box: { ...VIEWBOX.front },
};

function el<K extends keyof HTMLElementTagNameMap>(
	tag: K,
	props: Partial<HTMLElementTagNameMap[K]> = {},
	...kids: (Node | string)[]
) {
	const e = Object.assign(document.createElement(tag), props);
	e.append(...kids);
	return e;
}

// ---- Drawing ------------------------------------------------------------------------------------

const layerOf = (system: Structure["system"]): DrawnLayer => system;
const layerGroup = (layer: DrawnLayer) =>
	stage.querySelector<SVGGElement>(`g.layer-g[data-layer="${layer}"]`);

/** Draw a layer's shapes the first time it is shown in the current view. */
function fillLayer(layer: DrawnLayer) {
	const g = layerGroup(layer);
	if (!g || g.dataset.filled || state.layers[layer] === "hidden") return;
	g.innerHTML = layerMarkup(state.view, layer);
	g.dataset.filled = "1";
}

function renderView() {
	stage.innerHTML = DRAWN.map(
		(l) =>
			`<g class="layer-g" data-layer="${l}" data-state="${state.layers[l]}"></g>`,
	).join("");
	for (const l of DRAWN) fillLayer(l);
	stage.setAttribute(
		"aria-label",
		`Human body, ${VIEW_NAMES[state.view]} view. Tab to move through structures; Enter picks one; arrow keys pan; plus and minus zoom; 0 resets.`,
	);
	setBox(VIEWBOX[state.view]);
	refreshFocusable();
	highlight();
}

/** Only structures in visible layers take part in the tab order. */
function refreshFocusable() {
	for (const l of DRAWN) {
		const tab = state.layers[l] === "hidden" ? "-1" : "0";
		for (const s of layerGroup(l)?.querySelectorAll(".structure") ?? [])
			s.setAttribute("tabindex", tab);
	}
}

const shape = (id: string) =>
	stage.querySelector<SVGGraphicsElement>(`#${elementId(id)}`);

function highlight() {
	for (const e of stage.querySelectorAll(".picked, .related"))
		e.classList.remove("picked", "related");
	if (!state.picked) return;
	shape(state.picked)?.classList.add("picked");
	const p = part(state.picked);
	if (!p) return;
	for (const r of relations(p.structure))
		for (const id of r.ids)
			for (const d of drawnFor(id)) shape(d)?.classList.add("related");
}

/** The drawn ids of a structure in the current view (its own, or each side's). */
function drawnFor(structureId: string, view = state.view): string[] {
	const p = part(structureId);
	if (!p) return [];
	const ids = p.structure.sides
		? [p.structure.sides.right, p.structure.sides.left]
		: [p.structure.id];
	const drawn = drawnIds(view);
	return ids.filter((i) => drawn.has(i));
}

// ---- Layers panel -------------------------------------------------------------------------------

function renderLayers() {
	const box = $<HTMLElement>("#layers");
	box.replaceChildren();
	for (const layer of LAYERS) {
		const row = el(
			"div",
			{ className: "layer" },
			el("span", { textContent: layer.name }),
		);
		if (layer.planned || !DRAWN.includes(layer.id as DrawnLayer)) {
			row.dataset.planned = "";
			row.append(el("span", { className: "hint", textContent: "planned" }));
		} else {
			const id = layer.id as DrawnLayer;
			const tri = el("div", { className: "tri", role: "radiogroup" });
			tri.setAttribute("aria-label", `${layer.name} layer`);
			for (const [value, text] of CHOICES) {
				const input = document.createElement("input");
				input.type = "radio";
				input.name = `layer-${id}`;
				input.value = value;
				input.checked = state.layers[id] === value;
				input.addEventListener("change", () => setLayer(id, value));
				tri.append(el("label", {}, input, text));
			}
			row.append(tri);
		}
		box.append(row);
	}
}

function setLayer(layer: DrawnLayer, value: LayerState) {
	state.layers[layer] = value;
	const g = layerGroup(layer);
	if (g) g.dataset.state = value;
	fillLayer(layer);
	refreshFocusable();
	highlight();
	const input = document.querySelector<HTMLInputElement>(
		`input[name="layer-${layer}"][value="${value}"]`,
	);
	if (input) input.checked = true;
}

// ---- Details ------------------------------------------------------------------------------------

function showDetails() {
	const id = state.hovered ?? state.picked;
	const p = id ? part(id) : undefined;
	const heading = el("h2", { id: "details-h", textContent: "Details" });
	if (!p) {
		details.replaceChildren(
			heading,
			el("p", {
				className: "hint",
				textContent: "Hover over or pick a structure, or search for one.",
			}),
		);
		return;
	}
	const s = p.structure;
	const facts = el("dl");
	const fact = (term: string, value: string) =>
		facts.append(
			el("dt", { textContent: term }),
			el("dd", { textContent: value }),
		);
	fact("System", SYSTEM_NAMES[s.system]);
	if (s.count > 1)
		fact("Count", `${s.count}${s.sides ? `, ${s.count / 2} each side` : ""}`);
	if (s.synonyms.length) fact("Also", s.synonyms.join(", "));
	if (s.action) fact("Action", s.action);
	if (s.nerve) fact("Nerve", s.nerve);
	const seg = segmentOf(p.id) ?? (s.sides ? segmentOf(s.sides.right) : null);
	const segment = seg ? DATA.segments.find((x) => x.id === seg) : undefined;
	if (segment) fact("Segment", segment.name);
	const body: HTMLElement[] = [
		heading,
		el("h3", { textContent: label(p) }),
		el("p", {
			className: "latin",
			textContent: `${s.latin}${s.latinSource ? " (TA)" : ""}`,
			lang: "la",
		}),
		el("p", { textContent: s.description }),
		facts,
	];
	for (const r of relations(s)) {
		const list = el("div", { className: "rel" });
		for (const rid of r.ids) {
			const rp = part(rid);
			if (!rp) continue;
			const b = el("button", {
				type: "button",
				textContent: rp.structure.name,
			});
			b.addEventListener("click", () => jump(rid, p.side));
			list.append(b);
		}
		body.push(el("h4", { textContent: r.kind }), list);
	}
	if (s.notDrawn)
		body.push(
			el("p", { className: "hint", textContent: `Not drawn: ${s.notDrawn}` }),
		);
	if (id && id === state.picked && shape(id)) {
		const zoom = el("button", { type: "button", textContent: "Zoom to it" });
		zoom.addEventListener("click", () => zoomTo(id));
		body.push(zoom);
	}
	details.replaceChildren(...body);
}

// ---- Picking and jumping ------------------------------------------------------------------------

function pick(id: string | null) {
	state.picked = id;
	highlight();
	showDetails();
}

/** Pick a structure (preferring a side), switching view and showing its layer if needed, then zoom to it. */
function jump(structureId: string, side: Side | null = null) {
	const p = part(structureId);
	if (!p) return;
	const s = p.structure;
	const preferred = s.sides
		? [s.sides[side ?? "right"], s.sides[side === "left" ? "right" : "left"]]
		: [s.id];
	const views = [state.view, ...VIEWS.filter((v) => v !== state.view)];
	for (const v of views) {
		const drawn = drawnIds(v);
		const id = preferred.find((i) => drawn.has(i));
		if (!id) continue;
		if (v !== state.view) setView(v, false);
		const layer = layerOf(s.system);
		if (state.layers[layer] === "hidden") setLayer(layer, "shown");
		pick(id);
		zoomTo(id);
		return;
	}
	pick(s.sides ? (preferred[0] ?? s.id) : s.id); // not drawn anywhere: still show its details
}

function setView(view: View, keep = true) {
	const was = state.picked ? part(state.picked) : undefined;
	state.view = view;
	const radio = document.querySelector<HTMLInputElement>(
		`input[name="view"][value="${view}"]`,
	);
	if (radio) radio.checked = true;
	renderView();
	if (!keep || !was) return;
	// Keep the selection when it shows here: the same id, else the other side (the side view shows one side).
	const ids = drawnFor(was.structure.id);
	const keepId = ids.includes(was.id) ? was.id : ids[0];
	pick(keepId ?? null);
}

// ---- Hover tooltip ------------------------------------------------------------------------------

function structureAt(target: EventTarget | null): string | null {
	const e = (target as Element | null)?.closest?.(".structure");
	return e?.getAttribute("data-id") ?? null;
}

function hover(id: string | null, x = 0, y = 0) {
	if (id !== state.hovered) {
		state.hovered = id;
		showDetails();
	}
	const p = id ? part(id) : undefined;
	if (!p) {
		tip.hidden = true;
		return;
	}
	tip.textContent = label(p);
	tip.hidden = false;
	const r = wrap.getBoundingClientRect();
	tip.style.left = `${Math.min(x - r.left + 14, r.width - tip.offsetWidth - 4)}px`;
	tip.style.top = `${y - r.top + 14}px`;
}

// ---- Zoom and pan -------------------------------------------------------------------------------

const MIN_W = 6;

function setBox(b: { x: number; y: number; w: number; h: number }) {
	const base = VIEWBOX[state.view];
	const w = Math.min(Math.max(b.w, MIN_W), base.w * 1.5);
	const h = (w * base.h) / base.w;
	// Keep some of the body on screen.
	const x = Math.min(
		Math.max(b.x + (b.w - w) / 2, base.x - w * 0.8),
		base.x + base.w - w * 0.2,
	);
	const y = Math.min(
		Math.max(b.y + (b.h - h) / 2, base.y - h * 0.8),
		base.y + base.h - h * 0.2,
	);
	state.box = { x, y, w, h };
	stage.setAttribute("viewBox", `${x} ${y} ${w} ${h}`);
}

/** Zoom by `k` (above 1 zooms in) keeping the point at client (cx, cy) still. */
function zoomAt(k: number, cx?: number, cy?: number) {
	const b = state.box;
	const [px, py] =
		cx === undefined || cy === undefined
			? [b.x + b.w / 2, b.y + b.h / 2]
			: toSvg(cx, cy);
	setBox({
		x: px - (px - b.x) / k,
		y: py - (py - b.y) / k,
		w: b.w / k,
		h: b.h / k,
	});
}

function toSvg(cx: number, cy: number): [number, number] {
	const m = stage.getScreenCTM();
	if (!m) return [state.box.x + state.box.w / 2, state.box.y + state.box.h / 2];
	const p = new DOMPoint(cx, cy).matrixTransform(m.inverse());
	return [p.x, p.y];
}

function panBy(dxPx: number, dyPx: number) {
	const scale = stage.getScreenCTM()?.a || 1;
	setBox({
		...state.box,
		x: state.box.x - dxPx / scale,
		y: state.box.y - dyPx / scale,
	});
}

function zoomTo(id: string) {
	const e = shape(id);
	if (!e) return;
	const bb = e.getBBox();
	let m = e.getCTM();
	const root = stage.getCTM();
	if (m && root) m = root.inverse().multiply(m);
	const corners = [
		[bb.x, bb.y],
		[bb.x + bb.width, bb.y],
		[bb.x, bb.y + bb.height],
		[bb.x + bb.width, bb.y + bb.height],
	].map(([x, y]) =>
		m ? new DOMPoint(x, y).matrixTransform(m) : new DOMPoint(x, y),
	);
	const xs = corners.map((c) => c.x);
	const ys = corners.map((c) => c.y);
	const x0 = Math.min(...xs);
	const y0 = Math.min(...ys);
	const w = Math.max(...xs) - x0;
	const h = Math.max(...ys) - y0;
	const base = VIEWBOX[state.view];
	const fit = Math.max(w * 2.2, (h * 2.2 * base.w) / base.h, 14);
	const fh = (fit * base.h) / base.w;
	setBox({ x: x0 + w / 2 - fit / 2, y: y0 + h / 2 - fh / 2, w: fit, h: fh });
}

const pointers = new Map<number, { x: number; y: number }>();
let dragged = false;
let pinch = 0;

stage.addEventListener("pointerdown", (e) => {
	pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
	dragged = false;
	if (pointers.size === 2) {
		const [a, b] = [...pointers.values()] as [
			{ x: number; y: number },
			{ x: number; y: number },
		];
		pinch = Math.hypot(a.x - b.x, a.y - b.y);
	}
});
stage.addEventListener("pointermove", (e) => {
	const prev = pointers.get(e.pointerId);
	if (!prev) {
		if (e.pointerType === "mouse")
			hover(structureAt(e.target), e.clientX, e.clientY);
		return;
	}
	const now = { x: e.clientX, y: e.clientY };
	pointers.set(e.pointerId, now);
	if (pointers.size === 2) {
		const [a, b] = [...pointers.values()] as [
			{ x: number; y: number },
			{ x: number; y: number },
		];
		const dist = Math.hypot(a.x - b.x, a.y - b.y);
		if (pinch > 0) zoomAt(dist / pinch, (a.x + b.x) / 2, (a.y + b.y) / 2);
		pinch = dist;
		dragged = true;
		return;
	}
	if (!dragged && Math.hypot(now.x - prev.x, now.y - prev.y) < 4) {
		pointers.set(e.pointerId, prev); // too small to call a drag yet
		return;
	}
	if (!dragged) stage.setPointerCapture(e.pointerId);
	dragged = true;
	panBy(now.x - prev.x, now.y - prev.y);
});
const release = (e: PointerEvent) => {
	pointers.delete(e.pointerId);
	if (pointers.size < 2) pinch = 0;
};
stage.addEventListener("pointerup", release);
stage.addEventListener("pointercancel", release);
stage.addEventListener("pointerleave", () => hover(null));
stage.addEventListener(
	"wheel",
	(e) => {
		e.preventDefault();
		zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX, e.clientY);
	},
	{ passive: false },
);
stage.addEventListener("click", (e) => {
	if (dragged) return;
	pick(structureAt(e.target));
});
stage.addEventListener("keydown", (e) => {
	const id = structureAt(e.target);
	const step = 40;
	const keys: Record<string, () => void> = {
		ArrowLeft: () => panBy(step, 0),
		ArrowRight: () => panBy(-step, 0),
		ArrowUp: () => panBy(0, step),
		ArrowDown: () => panBy(0, -step),
		"+": () => zoomAt(1.25),
		"=": () => zoomAt(1.25),
		"-": () => zoomAt(0.8),
		"0": () => setBox(VIEWBOX[state.view]),
		Enter: () => id && pick(id),
		" ": () => id && pick(id),
		Escape: () => pick(null),
	};
	const act = keys[e.key];
	if (!act) return;
	e.preventDefault();
	act();
});
stage.addEventListener("focusin", (e) => {
	const id = structureAt(e.target);
	if (!id) return;
	const r = (e.target as Element).getBoundingClientRect();
	hover(id, r.left + r.width / 2, r.top + r.height / 2);
});
stage.addEventListener("focusout", () => hover(null));

$("#zoom-in").addEventListener("click", () => zoomAt(1.25));
$("#zoom-out").addEventListener("click", () => zoomAt(0.8));
$("#zoom-reset").addEventListener("click", () => setBox(VIEWBOX[state.view]));
for (const r of document.querySelectorAll<HTMLInputElement>(
	'input[name="view"]',
)) {
	r.addEventListener("change", () => setView(r.value as View));
}

// ---- Search -------------------------------------------------------------------------------------

let found: Structure[] = [];
let active = -1;

function renderResults() {
	results.replaceChildren(
		...found.map((s, i) => {
			const li = el(
				"li",
				{ id: `result-${i}`, role: "option" },
				s.name,
				el("small", { textContent: s.latin }),
			);
			li.setAttribute("aria-selected", String(i === active));
			li.addEventListener("mousedown", (e) => {
				e.preventDefault();
				choose(i);
			});
			return li;
		}),
	);
	if (!found.length && q.value.trim())
		results.append(el("div", { className: "none", textContent: "No match" }));
	const open = q.value.trim() !== "";
	results.hidden = !open;
	q.setAttribute("aria-expanded", String(open));
	if (active >= 0) q.setAttribute("aria-activedescendant", `result-${active}`);
	else q.removeAttribute("aria-activedescendant");
}

function choose(i: number) {
	const s = found[i];
	if (!s) return;
	q.value = s.name;
	found = [];
	active = -1;
	renderResults();
	results.hidden = true;
	q.setAttribute("aria-expanded", "false");
	jump(s.id);
}

q.addEventListener("input", () => {
	found = search(q.value);
	active = found.length ? 0 : -1;
	renderResults();
});
q.addEventListener("keydown", (e) => {
	if (e.key === "ArrowDown" || e.key === "ArrowUp") {
		e.preventDefault();
		if (!found.length) return;
		active =
			(active + (e.key === "ArrowDown" ? 1 : -1) + found.length) % found.length;
		renderResults();
	} else if (e.key === "Enter") {
		e.preventDefault();
		choose(Math.max(active, 0));
	} else if (e.key === "Escape") {
		q.value = "";
		found = [];
		renderResults();
	}
});
q.addEventListener("blur", () => {
	results.hidden = true;
	q.setAttribute("aria-expanded", "false");
});

// ---- Sources ------------------------------------------------------------------------------------

$("#sources").replaceChildren(
	...DATA.sources.map((s) =>
		el(
			"li",
			{},
			s.url
				? el("a", { href: s.url, textContent: s.name, rel: "noopener" })
				: s.name,
			` (${s.license}): ${s.use}`,
		),
	),
);

renderLayers();
renderView();
showDetails();
stage.dataset.ready = "1";
