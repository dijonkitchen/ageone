// The page: renders the data, saves every change to localStorage, exports and imports backups, and activates a
// downloaded update at launch. All text goes in with textContent.

import { backupDue, heart, nextAction, trends, vo2max, week } from "./advice";
import { dayOf } from "./dates";
import { ZONES, type Zone, zoneRange } from "./formulas";
import {
	addEntry,
	type Data,
	emptyData,
	exported,
	KIND_INFO,
	KINDS,
	type Kind,
	parse,
	removeEntry,
	serialize,
	setProfile,
	setTargets,
} from "./store";

const KEY = "simplefit";
const $ = <T extends HTMLElement>(id: string) =>
	document.getElementById(id) as T;

function read(): Data {
	let raw: string | null = null;
	try {
		raw = localStorage.getItem(KEY);
	} catch {}
	if (!raw) return emptyData();
	try {
		return parse(raw);
	} catch {
		// Never overwrite data we couldn't read: keep it aside for a later import.
		try {
			localStorage.setItem(`${KEY}-unreadable-${Date.now()}`, raw);
		} catch {}
		return emptyData();
	}
}

let data = read();
const today = () => dayOf(new Date());

function save(next: Data): void {
	data = next;
	try {
		localStorage.setItem(KEY, serialize(data));
	} catch {
		$("backup-status").textContent =
			"Couldn't save on this device: export a backup now.";
	}
	render();
}

function el<K extends keyof HTMLElementTagNameMap>(
	tag: K,
	text = "",
	className = "",
): HTMLElementTagNameMap[K] {
	const e = document.createElement(tag);
	if (text) e.textContent = text;
	if (className) e.className = className;
	return e;
}

function metric(
	label: string,
	value: string,
	bar?: [number, number],
): HTMLElement {
	const row = el("div", "", "metric");
	row.append(el("span", label));
	if (bar) {
		const p = el("progress");
		p.max = Math.max(1, bar[1]);
		p.value = Math.min(bar[0], p.max);
		row.append(p);
	} else row.append(el("span"));
	row.append(el("strong", value));
	return row;
}

function sparkline(points: number[]): SVGSVGElement {
	const ns = "http://www.w3.org/2000/svg";
	const svg = document.createElementNS(ns, "svg");
	svg.setAttribute("viewBox", "0 0 100 28");
	svg.setAttribute("preserveAspectRatio", "none");
	svg.setAttribute("aria-hidden", "true");
	const real = points.filter((p) => !Number.isNaN(p));
	if (real.length) {
		const lo = Math.min(...real);
		const hi = Math.max(...real);
		const xy = points
			.map((p, i) =>
				Number.isNaN(p)
					? null
					: `${(i / Math.max(1, points.length - 1)) * 100},${24 - ((p - lo) / (hi - lo || 1)) * 20}`,
			)
			.filter(Boolean)
			.join(" ");
		const line = document.createElementNS(ns, "polyline");
		line.setAttribute("points", xy);
		line.setAttribute("fill", "none");
		line.setAttribute("stroke", "currentColor");
		line.setAttribute("stroke-width", "2");
		line.setAttribute("vector-effect", "non-scaling-stroke");
		svg.append(line);
	}
	return svg;
}

function render(): void {
	const day = today();
	const h = heart(data, day);
	const v = vo2max(data, day);
	const done = week(data, day);

	const due = backupDue(data, new Date());
	const reminder = $("backup-reminder");
	reminder.hidden = !due;
	reminder.textContent = data.lastExport
		? "It has been over 30 days since your last backup. Export one below."
		: "You haven't backed up yet. Export a copy below.";

	$("next").textContent = nextAction(data, day).text;

	const weekEl = $("week");
	weekEl.replaceChildren(
		metric("Zone 2", `${done.zone2} / ${data.targets.zone2} min`, [
			done.zone2,
			data.targets.zone2,
		]),
		metric("Zone 4", `${done.zone4} / ${data.targets.zone4} min`, [
			done.zone4,
			data.targets.zone4,
		]),
		metric("Strength", `${done.strength} / ${data.targets.strength}`, [
			done.strength,
			data.targets.strength,
		]),
		metric("Resting HR", h.rest === null ? "not logged" : `${h.rest} bpm`),
		metric(
			"VO₂max",
			v === null
				? "needs resting HR and age"
				: `${v.value} ${v.measured ? "measured" : "estimated"}${v.band ? `, ${v.band}` : ""}`,
		),
	);

	const select = $<HTMLSelectElement>("log-kind");
	if (!select.options.length)
		for (const kind of KINDS) {
			const o = el(
				"option",
				`${KIND_INFO[kind].label} (${KIND_INFO[kind].unit})`,
			);
			o.value = kind;
			select.append(o);
		}
	const dayInput = $<HTMLInputElement>("log-day");
	dayInput.max = day;
	if (!dayInput.value) dayInput.value = day;

	const list = $("entries");
	list.replaceChildren(
		...data.entries
			.slice(-10)
			.reverse()
			.map((e) => {
				const li = el("li");
				li.append(
					el(
						"span",
						`${e.day}  ${KIND_INFO[e.kind].label}: ${e.value} ${e.value === 1 ? KIND_INFO[e.kind].unit.replace(/s$/, "") : KIND_INFO[e.kind].unit}`,
					),
				);
				const del = el("button", "Delete");
				del.type = "button";
				del.setAttribute(
					"aria-label",
					`Delete ${KIND_INFO[e.kind].label} on ${e.day}`,
				);
				del.addEventListener("click", () => save(removeEntry(data, e.id)));
				li.append(del);
				return li;
			}),
	);

	$("trends").replaceChildren(
		...trends(data, day).map((t) => {
			const row = el("div", "", "metric");
			row.append(
				el("span", KIND_INFO[t.kind].label),
				sparkline(t.points),
				el("span", t.direction, t.direction),
			);
			return row;
		}),
	);

	const zones = $("zones");
	if (h.max === null || h.rest === null)
		zones.replaceChildren(
			el(
				"p",
				"Add your birth year (or measured max heart rate) and log a resting heart rate to see your zones.",
			),
		);
	else {
		const table = el("table");
		const head = el("tr");
		head.append(el("th", "Zone"), el("th", "Heart rate"), el("th", "Reserve"));
		table.append(head);
		for (const z of Object.keys(ZONES).map(Number) as Zone[]) {
			const [lo, hi] = zoneRange(z, h.rest, h.max);
			const [a, b] = ZONES[z];
			const tr = el("tr");
			tr.append(
				el("td", String(z)),
				el("td", `${lo}-${hi} bpm`),
				el("td", `${a * 100}-${b * 100}%`),
			);
			table.append(tr);
		}
		zones.replaceChildren(
			el(
				"p",
				`Max ${h.max} bpm (${h.measuredMax ? "measured" : "estimated from age"}), resting ${h.rest} bpm.`,
			),
			table,
		);
	}

	const form = $<HTMLFormElement>("settings");
	const set = (name: string, value: number | string | null) => {
		const input = form.elements.namedItem(name) as
			| HTMLInputElement
			| HTMLSelectElement;
		if (document.activeElement !== input)
			input.value = value === null ? "" : String(value);
	};
	set("birthYear", data.profile.birthYear);
	set("sex", data.profile.sex);
	set("maxHr", data.profile.maxHr);
	set("zone2", data.targets.zone2);
	set("zone4", data.targets.zone4);
	set("strength", data.targets.strength);

	$("backup-status").textContent = data.lastExport
		? `Last export: ${new Date(data.lastExport).toLocaleDateString()}.`
		: "Never exported.";
}

$<HTMLFormElement>("log-form").addEventListener("submit", (event) => {
	event.preventDefault();
	const kind = $<HTMLSelectElement>("log-kind").value as Kind;
	const value = Number($<HTMLInputElement>("log-value").value);
	const day = $<HTMLInputElement>("log-day").value;
	try {
		save(addEntry(data, { id: crypto.randomUUID(), day, kind, value }));
		$("log-error").textContent = "";
		$<HTMLInputElement>("log-value").value = "";
	} catch (e) {
		$("log-error").textContent = (e as Error).message;
	}
});

$<HTMLFormElement>("settings").addEventListener("change", (event) => {
	const input = event.target as HTMLInputElement;
	const n = input.value === "" ? null : Number(input.value);
	if (input.name === "sex")
		save(
			setProfile(data, {
				sex: (input.value || null) as Data["profile"]["sex"],
			}),
		);
	else if (input.name === "birthYear" || input.name === "maxHr")
		save(setProfile(data, { [input.name]: n }));
	else if (n !== null && n >= 0) save(setTargets(data, { [input.name]: n }));
});

$("export").addEventListener("click", () => {
	const at = new Date().toISOString();
	const next = exported(data, at);
	const blob = new Blob([JSON.stringify(next, null, 2)], {
		type: "application/json",
	});
	const a = el("a");
	a.href = URL.createObjectURL(blob);
	a.download = `simplefit-${today()}.json`;
	a.click();
	setTimeout(() => URL.revokeObjectURL(a.href), 10_000);
	save(next);
});

$<HTMLInputElement>("import").addEventListener("change", async (event) => {
	const input = event.target as HTMLInputElement;
	const file = input.files?.[0];
	input.value = "";
	if (!file) return;
	try {
		const imported = parse(await file.text());
		const n = imported.entries.length;
		if (
			data.entries.length &&
			!confirm(
				`Replace the ${data.entries.length} entries here with the ${n} in the backup?`,
			)
		)
			return;
		save(imported);
		$("backup-status").textContent = `Imported ${n} entries.`;
	} catch (e) {
		$("backup-status").textContent =
			`Couldn't import: ${(e as Error).message}.`;
	}
});

// An update downloaded on an earlier launch waits; activate it now, before the app is used, then reload once.
async function update(): Promise<void> {
	if (!("serviceWorker" in navigator)) return;
	const reg = await navigator.serviceWorker.register("sw.js");
	if (reg.waiting && navigator.serviceWorker.controller) {
		navigator.serviceWorker.addEventListener(
			"controllerchange",
			() => location.reload(),
			{ once: true },
		);
		reg.waiting.postMessage("activate");
	}
}

render();
update().catch(() => {});
navigator.storage?.persist?.().catch(() => {});
