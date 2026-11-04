// The page: draws the map, reads keys, and opens the codex, lessons, sandbox, and new-run dialogs.
// The run itself is the engine's: the page only sends inputs, which it also saves for replay.
import type { QuickJSWASMModule } from "quickjs-emscripten-core";
import { CONCEPTS } from "../concepts";
import {
	type Env,
	ITEMS,
	inventoryPolicy,
	MONSTERS,
	newRun,
	remembers,
	step,
} from "../core/engine";
import { index, SHRINE, STAIRS, tileAt } from "../core/grid";
import { seedFrom } from "../core/rng";
import { loadSandbox, PlayerCode } from "../core/sandbox";
import type { Concept, State } from "../core/types";
import { el, lessonView, stepper } from "./lesson";
import { loadMeta, loadRun, type SavedRun, saveMeta, saveRun } from "./store";

const $ = <T extends Element>(sel: string) => document.querySelector(sel) as T;
const byId = new Map(CONCEPTS.map((c) => [c.id, c]));

let meta = loadMeta();
let qjs: QuickJSWASMModule | null = null;
const compiled = new Map<string, PlayerCode>(); // concept id → the player's loaded code

const owner = (fn: string) =>
	CONCEPTS.find((c) => c.code?.exports.includes(fn));

const env: Env = {
	concepts: CONCEPTS,
	code(fn) {
		const c = owner(fn);
		const code = c && meta.useCode[c.id] ? compiled.get(c.id) : undefined;
		return code ? (...args: unknown[]) => code.call(fn, ...args) : null;
	},
	codeFailed(fn) {
		const c = owner(fn);
		if (!c) return;
		meta.useCode[c.id] = false;
		saveMeta(meta);
	},
};

let run: SavedRun;
let s: State;

const has = (feature: string) =>
	CONCEPTS.some(
		(c) => s.unlocked.includes(c.id) && c.hooks.features?.includes(feature),
	);

function start(seed: number, learned = meta.unlocked, inputs: string[] = []) {
	run = { seed, learned: [...learned], inputs: [] };
	s = newRun(env, seed, learned);
	for (const i of inputs) act(i, false);
	saveRun(run);
	render();
}

function act(input: string, draw = true) {
	if (s.over) return;
	run.inputs.push(input);
	const wasOnShrine = tileAt(s.floor, s.player.x, s.player.y) === SHRINE;
	step(env, s, input);
	for (const id of s.unlocked)
		if (!meta.unlocked.includes(id)) meta.unlocked.push(id);
	saveMeta(meta);
	saveRun(s.over ? null : run);
	if (!draw) return;
	render();
	const onShrine = tileAt(s.floor, s.player.x, s.player.y) === SHRINE;
	if (onShrine && !wasOnShrine && s.pages.length) openShrine();
}

// ---- Drawing ------------------------------------------------------------------------------------

const esc = (c: string) =>
	c === "<" ? "&lt;" : c === ">" ? "&gt;" : c === "&" ? "&amp;" : c;

function render() {
	const f = s.floor;
	const visible = new Set(s.visible);
	const memory = remembers(env, s);
	const things = new Map<number, [string, string]>();
	for (const it of s.items)
		things.set(index(f, it.x, it.y), [
			ITEMS[it.kind].glyph,
			it.kind === "page" ? "page" : "item",
		]);
	for (const m of s.monsters)
		things.set(index(f, m.x, m.y), [MONSTERS[m.kind]?.glyph ?? "?", "monster"]);
	things.set(index(f, s.player.x, s.player.y), ["@", "player"]);
	let html = "";
	for (let y = 0; y < f.h; y++) {
		for (let x = 0; x < f.w; x++) {
			const i = index(f, x, y);
			const t = f.tiles[i] as string;
			const kind =
				t === "#"
					? "wall"
					: t === SHRINE
						? "shrine"
						: t === STAIRS
							? "stairs"
							: "floor";
			if (visible.has(i)) {
				const [g, cls] = things.get(i) ?? [t, kind];
				html += `<span class="${cls}">${esc(g)}</span>`;
			} else if (memory && f.seen[i])
				html += `<span class="dim">${esc(t)}</span>`;
			else html += " ";
		}
		html += "\n";
	}
	$("#map").innerHTML = html;
	const p = s.player;
	const parts = [
		`Depth ${s.depth}`,
		`HP ${p.hp}/${p.maxHp}`,
		`Turn ${s.turn}`,
		`Learned ${s.unlocked.length}/${CONCEPTS.length}`,
	];
	if (s.pages.length)
		parts.push(`Pages: ${s.pages.map((id) => byId.get(id)?.name).join(", ")}`);
	if (p.haste) parts.push(`Hasted ${p.haste}`);
	if (has("seeds")) parts.push(`Seed ${s.seed}`);
	if (s.over) parts.push("Dead: press N (shift+n) for a new run");
	$("#status").textContent = parts.join(" · ");
	$("#map").setAttribute(
		"aria-label",
		`Depth ${s.depth} map. ${describeNearby()}`,
	);
	$("#log").replaceChildren(
		...s.log.slice(-5).map((m) => el("li", { textContent: m })),
	);
	const policy = inventoryPolicy(env, s);
	$("#pack").replaceChildren(
		...s.inventory.map((st, k) =>
			el("li", {
				textContent: `${st.kind}${st.count > 1 ? ` ×${st.count}` : ""}`,
				title: `${ITEMS[st.kind].about} Press ${k + 1} to use.`,
			}),
		),
	);
	$("#pack-note").textContent =
		`${s.inventory.length ? "" : "Empty. "}${policy.stacks ? `${s.inventory.length}/${policy.limit} kinds, stacked by name` : `${s.inventory.length}/${policy.limit} slots`}`;
	renderKeys();
	document.documentElement.style.setProperty("--size", `${meta.size}px`);
}

/** A sentence for screen readers about what is next to the player. */
function describeNearby(): string {
	const seen = new Set(s.visible);
	const near = s.monsters
		.filter((m) => seen.has(index(s.floor, m.x, m.y)))
		.map(
			(m) =>
				`${MONSTERS[m.kind]?.name} ${dir(m.x - s.player.x, m.y - s.player.y)}`,
		);
	const items = s.items
		.filter((i) => seen.has(index(s.floor, i.x, i.y)))
		.map((i) => `${i.kind} ${dir(i.x - s.player.x, i.y - s.player.y)}`);
	const here = tileAt(s.floor, s.player.x, s.player.y);
	return [
		here === SHRINE
			? "You stand on a shrine."
			: here === STAIRS
				? "You stand on stairs down."
				: "",
		near.length ? `In sight: ${near.join(", ")}.` : "No monsters in sight.",
		items.length ? `Items: ${items.join(", ")}.` : "",
	].join(" ");
}

const dir = (dx: number, dy: number) =>
	`${Math.max(Math.abs(dx), Math.abs(dy))} ${dy < 0 ? "north" : dy > 0 ? "south" : ""}${dx < 0 ? "west" : dx > 0 ? "east" : ""}`.trim();

function renderKeys() {
	const rows: [string, string][] = [
		["arrows hjkl", "move (yubn diagonals; numpad works too)"],
		[".", "wait a turn"],
		[">", "go down stairs"],
		["1-9", "use an item from the pack"],
	];
	for (const c of CONCEPTS)
		if (s.unlocked.includes(c.id))
			for (const a of Object.values(c.hooks.actions ?? {}))
				rows.push([a.key, a.label]);
	rows.push(
		["s", "study pages (on a shrine)"],
		["c", "codex"],
		["x", "sandbox"],
		["N", "new run"],
		["[ ]", "text size"],
	);
	$("#keys").replaceChildren(
		...rows.flatMap(([k, v]) => [
			el("dt", { textContent: k }),
			el("dd", { textContent: v }),
		]),
	);
}

// ---- Dialogs ------------------------------------------------------------------------------------

let stopFrames: (() => void) | null = null;

function openDialog(d: HTMLDialogElement) {
	if (!d.open) d.showModal();
}
for (const d of document.querySelectorAll("dialog")) {
	d.querySelector(".close")?.addEventListener("click", () => d.close());
	d.addEventListener("close", () => {
		stopFrames?.();
		stopFrames = null;
		render();
	});
}

const codeHooks = (c: Concept) => ({
	qjs,
	saved: meta.code[c.id],
	passed(source: string, code: PlayerCode) {
		compiled.get(c.id)?.dispose();
		compiled.set(c.id, code);
		meta.code[c.id] = source;
		meta.useCode[c.id] = true;
		saveMeta(meta);
	},
});

function openLesson(c: Concept, learnable: boolean) {
	const d = $<HTMLDialogElement>("#lesson");
	$("#lesson-h").textContent = c.name;
	const learned = () => {
		act(`learn:${c.id}`);
		$("#lesson-body").prepend(
			el("p", {
				className: "verdict right",
				textContent: `You learned ${c.name}: ${c.unlocks}`,
			}),
		);
	};
	const view = lessonView(c, codeHooks(c), learnable ? learned : null);
	stopFrames = view.stop;
	$("#lesson-body").replaceChildren(view.node);
	openDialog(d);
}

function openShrine() {
	const onShrine = tileAt(s.floor, s.player.x, s.player.y) === SHRINE;
	if (!onShrine) {
		s.log.push("Stand on a shrine (_) to study.");
		render();
		return;
	}
	const ready = s.pages
		.map((id) => byId.get(id))
		.filter((c): c is Concept => !!c);
	if (ready.length === 1 && ready[0]) {
		openLesson(ready[0], true);
		return;
	}
	$("#lesson-h").textContent = "Shrine";
	$("#lesson-body").replaceChildren(
		el("p", {
			textContent: ready.length
				? "Which page will you study?"
				: "You carry no codex pages. Find them on each floor (?).",
		}),
		...ready.map((c) => {
			const b = el("button", { type: "button", textContent: c.name });
			b.addEventListener("click", () => openLesson(c, true));
			return b;
		}),
	);
	openDialog($("#lesson"));
}

function openCodex() {
	const body = $("#codex-body");
	body.replaceChildren();
	for (const tier of [1, 2, 3, 4] as const) {
		const list = CONCEPTS.filter((c) => c.tier === tier);
		if (!list.length) continue;
		const section = el(
			"section",
			{ className: "tier" },
			el("h3", { textContent: `Tier ${tier}` }),
		);
		for (const c of list) {
			const learned = s.unlocked.includes(c.id);
			const page = s.pages.includes(c.id);
			const missing = c.requires
				.filter((r) => !s.unlocked.includes(r))
				.map((r) => byId.get(r)?.name);
			const badge = el("span", {
				className: `badge ${learned ? "learned" : page ? "page" : ""}`,
				textContent: learned
					? "learned"
					: page
						? "page in hand"
						: missing.length
							? "locked"
							: "find its page",
			});
			const card = el(
				"div",
				{ className: "concept" },
				el("h4", {}, c.name, badge),
				el("p", { textContent: `Unlocks: ${c.unlocks}` }),
			);
			if (c.requires.length)
				card.append(
					el("p", {
						className: "hint",
						textContent: `Needs: ${c.requires.map((r) => byId.get(r)?.name).join(", ")}`,
					}),
				);
			if (learned) {
				card.append(
					el(
						"p",
						{ className: "hint" },
						`Time ${c.complexity.time}; space ${c.complexity.space}. `,
						el("a", {
							href: c.reading.url,
							textContent: c.reading.title,
							target: "_blank",
							rel: "noopener",
						}),
					),
				);
				const review = el("button", {
					type: "button",
					textContent: c.code ? "Review, or write it yourself" : "Review",
				});
				review.addEventListener("click", () => {
					$<HTMLDialogElement>("#codex").close();
					openLesson(c, false);
				});
				card.append(review);
				if (c.code && meta.code[c.id]) {
					const box = el("input", {
						type: "checkbox",
						checked: !!meta.useCode[c.id] && compiled.has(c.id),
					});
					box.addEventListener("change", () => {
						meta.useCode[c.id] = box.checked;
						saveMeta(meta);
						if (box.checked) compile(c);
					});
					card.append(
						el("label", {}, box, " Run my code instead of the reference"),
					);
				}
			} else if (page) {
				const look = el("button", {
					type: "button",
					textContent: "Read the lesson",
				});
				look.addEventListener("click", () => {
					$<HTMLDialogElement>("#codex").close();
					openLesson(c, false);
				});
				card.append(
					look,
					el("p", {
						className: "hint",
						textContent: "Learn it at a shrine (_).",
					}),
				);
			}
			section.append(card);
		}
		body.append(section);
	}
	openDialog($("#codex"));
}

function compile(c: Concept) {
	const source = meta.code[c.id];
	const trial = c.code;
	if (!qjs || !source || !trial || compiled.has(c.id)) return;
	const code = new PlayerCode(qjs, source, trial.exports);
	if (code.error) {
		code.dispose();
		meta.useCode[c.id] = false;
		saveMeta(meta);
	} else compiled.set(c.id, code);
}

function openSandbox() {
	const pick = $<HTMLSelectElement>("#sandbox-pick");
	const learned = CONCEPTS.filter((c) => s.unlocked.includes(c.id));
	const body = $("#sandbox-body");
	if (!learned.length) {
		pick.replaceChildren();
		body.replaceChildren(
			el("p", {
				textContent: "Learn a concept first: its algorithm then runs here.",
			}),
		);
		openDialog($("#sandbox"));
		return;
	}
	pick.replaceChildren(
		...learned.map((c) =>
			el("option", {
				value: c.id,
				textContent: `${c.name}${c.sandbox ? " (on this floor)" : " (demo)"}`,
			}),
		),
	);
	const show = () => {
		stopFrames?.();
		const c = byId.get(pick.value);
		if (!c) return;
		const seed = Math.floor(Math.random() * 1e9);
		const frames = c.sandbox
			? c.sandbox(s.floor, [s.player.x, s.player.y], seed)
			: c.lesson.frames(seed);
		const view = stepper(frames);
		stopFrames = view.stop;
		body.replaceChildren(view.node);
	};
	pick.onchange = show;
	show();
	openDialog($("#sandbox"));
}

function download(name: string, text: string) {
	const a = el("a", {
		href: URL.createObjectURL(new Blob([text], { type: "application/json" })),
		download: name,
	});
	document.body.append(a);
	a.click();
	a.remove();
	window.setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function openRun() {
	const body = $("#run-body");
	const random = el("button", {
		type: "button",
		textContent: "Start a new run",
	});
	random.addEventListener("click", () => {
		$<HTMLDialogElement>("#run").close();
		start(Math.floor(Math.random() * 2 ** 32));
	});
	body.replaceChildren(el("div", { className: "controls" }, random));
	if (has("seeds")) {
		const today = new Date().toISOString().slice(0, 10);
		const seedBox = el("input", {
			type: "text",
			placeholder: "a number or any words",
			value: String(s.seed),
		});
		seedBox.setAttribute("aria-label", "Seed");
		const go = el("button", {
			type: "button",
			textContent: "Start from this seed",
		});
		go.addEventListener("click", () => {
			const v = seedBox.value.trim();
			$<HTMLDialogElement>("#run").close();
			start(/^\d+$/.test(v) ? Number(v) >>> 0 : seedFrom(v));
		});
		const daily = el("button", {
			type: "button",
			textContent: `Daily run (${today})`,
		});
		daily.addEventListener("click", () => {
			$<HTMLDialogElement>("#run").close();
			start(seedFrom(`daily ${today}`));
		});
		const save = el("button", {
			type: "button",
			textContent: "Save this run's replay",
		});
		save.addEventListener("click", () =>
			download(
				`replay-${run.seed}.json`,
				JSON.stringify(
					{ game: "algorithm-roguelike", version: 1, ...run },
					null,
					1,
				),
			),
		);
		const file = el("input", {
			type: "file",
			accept: "application/json,.json",
		});
		file.setAttribute("aria-label", "Load a replay file");
		file.addEventListener("change", async () => {
			const text = await file.files?.[0]?.text();
			try {
				const r = JSON.parse(text ?? "") as SavedRun;
				if (
					!Number.isInteger(r.seed) ||
					!Array.isArray(r.inputs) ||
					!Array.isArray(r.learned)
				)
					throw new Error("not a replay");
				$<HTMLDialogElement>("#run").close();
				start(
					r.seed,
					r.learned.filter((id) => byId.has(id)),
					r.inputs.map(String),
				);
			} catch {
				body.append(
					el("p", {
						className: "verdict wrong",
						textContent: "That file isn't a replay from this game.",
					}),
				);
			}
		});
		body.append(
			el("h3", { textContent: "Seeds and replays" }),
			el("div", { className: "controls" }, seedBox, go, daily),
			el(
				"div",
				{ className: "controls" },
				save,
				el("label", {}, "Load a replay: ", file),
			),
			el("p", {
				className: "hint",
				textContent:
					"A replay is the seed, what was learned before the run, and every key. Loading one plays it back to where it ended, and you carry on from there.",
			}),
		);
	}
	const forget = el("button", {
		type: "button",
		textContent: "Forget everything learned",
	});
	forget.addEventListener("click", () => {
		if (
			!window.confirm(
				"Forget every concept and all your code, and start as a new player?",
			)
		)
			return;
		for (const c of compiled.values()) c.dispose();
		compiled.clear();
		meta = { ...meta, unlocked: [], code: {}, useCode: {} };
		saveMeta(meta);
		$<HTMLDialogElement>("#run").close();
		start(Math.floor(Math.random() * 2 ** 32), []);
	});
	body.append(el("h3", { textContent: "Start over" }), forget);
	openDialog($("#run"));
}

// ---- Keys ---------------------------------------------------------------------------------------

const MOVES: Record<string, [number, number]> = {
	ArrowLeft: [-1, 0],
	ArrowRight: [1, 0],
	ArrowUp: [0, -1],
	ArrowDown: [0, 1],
	h: [-1, 0],
	l: [1, 0],
	k: [0, -1],
	j: [0, 1],
	y: [-1, -1],
	u: [1, -1],
	b: [-1, 1],
	n: [1, 1],
	Home: [-1, -1],
	PageUp: [1, -1],
	End: [-1, 1],
	PageDown: [1, 1],
};
const NUMPAD: Record<string, [number, number]> = {
	Numpad1: [-1, 1],
	Numpad2: [0, 1],
	Numpad3: [1, 1],
	Numpad4: [-1, 0],
	Numpad6: [1, 0],
	Numpad7: [-1, -1],
	Numpad8: [0, -1],
	Numpad9: [1, -1],
};

document.addEventListener("keydown", (e) => {
	if (
		document.querySelector("dialog[open]") ||
		e.ctrlKey ||
		e.metaKey ||
		e.altKey
	)
		return;
	if (
		e.target instanceof HTMLInputElement ||
		e.target instanceof HTMLTextAreaElement ||
		e.target instanceof HTMLSelectElement
	)
		return;
	const move = NUMPAD[e.code] ?? MOVES[e.key];
	let done = true;
	if (move) act(`move:${move[0]},${move[1]}`);
	else if (e.key === "N") openRun();
	else if (e.key === "." || e.code === "Numpad5") act("wait");
	else if (e.key === ">") act("descend");
	else if (/^Digit[1-9]$/.test(e.code)) act(`use:${e.code.slice(5)}`);
	else if (e.key === "c") openCodex();
	else if (e.key === "x") openSandbox();
	else if (e.key === "s") openShrine();
	else if (e.key === "[") resize(-1);
	else if (e.key === "]") resize(1);
	else {
		const action = CONCEPTS.filter((c) => s.unlocked.includes(c.id))
			.flatMap((c) => Object.entries(c.hooks.actions ?? {}))
			.find(([, a]) => a.key === e.key);
		if (action) act(`act:${action[0]}`);
		else done = false;
	}
	if (done) e.preventDefault();
});

function resize(d: number) {
	meta.size = Math.max(12, Math.min(28, meta.size + d * 2));
	saveMeta(meta);
	render();
}

$("#smaller").addEventListener("click", () => resize(-1));
$("#bigger").addEventListener("click", () => resize(1));
$("#open-codex").addEventListener("click", openCodex);
$("#open-sandbox").addEventListener("click", openSandbox);
$("#open-run").addEventListener("click", openRun);

// ---- Start --------------------------------------------------------------------------------------

const saved = loadRun();
if (saved)
	start(
		saved.seed,
		saved.learned.filter((id) => byId.has(id)),
		saved.inputs,
	);
else start(Math.floor(Math.random() * 2 ** 32));
document.body.dataset.ready = "1";

loadSandbox()
	.then((m) => {
		qjs = m;
		for (const c of CONCEPTS) if (meta.useCode[c.id]) compile(c);
		document.body.dataset.sandbox = "1";
	})
	.catch(() => {
		// Without the sandbox only code mode is missing; the reference runs everything.
	});
