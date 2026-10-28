// The page: wires the pure modules to the DOM, IndexedDB, and the service worker. Every feed string goes in
// as text, except article HTML, which goes in only after sanitize().

import { fetchFeed, normalizeFeedUrl } from "./fetch";
import { parseOpml, toOpml } from "./opml";
import { IMAGE_PLACEHOLDER_CLASS, sanitize } from "./sanitize";
import * as store from "./store";
import { ROLES, summarize } from "./summarize";

const DB = "fread";
let state = store.emptyState();
let current: { feed: string | null; item: string | null } = {
	feed: null,
	item: null,
};

// Persistence: one IndexedDB record holding the state as JSON.

function idb(): Promise<IDBDatabase> {
	return new Promise((resolve, reject) => {
		const open = indexedDB.open(DB, 1);
		open.onupgradeneeded = () => open.result.createObjectStore("kv");
		open.onsuccess = () => resolve(open.result);
		open.onerror = () => reject(open.error);
	});
}

async function load(): Promise<store.State> {
	const db = await idb();
	return new Promise((resolve) => {
		const get = db.transaction("kv").objectStore("kv").get("state");
		get.onsuccess = () =>
			resolve(
				store.deserialize(typeof get.result === "string" ? get.result : null),
			);
		get.onerror = () => resolve(store.emptyState());
	});
}

let saving: Promise<void> = Promise.resolve();
function save(): void {
	const json = store.serialize(state);
	saving = saving.then(
		async () =>
			new Promise<void>((resolve) => {
				idb().then((db) => {
					const tx = db.transaction("kv", "readwrite");
					tx.objectStore("kv").put(json, "state");
					tx.oncomplete = () => resolve();
					tx.onerror = () => resolve();
				});
			}),
	);
}

function update(next: store.State): void {
	if (next === state) return;
	state = next;
	save();
	render();
}

// DOM helpers

const $ = <T extends HTMLElement>(selector: string) =>
	document.querySelector(selector) as T;

function el<K extends keyof HTMLElementTagNameMap>(
	tag: K,
	props: Partial<HTMLElementTagNameMap[K]> = {},
	...kids: (Node | string)[]
) {
	const node = Object.assign(document.createElement(tag), props);
	node.append(...kids);
	return node;
}

function status(text: string): void {
	$("#status").textContent = text;
}

const dateText = (iso: string | null) =>
	iso
		? new Date(iso).toLocaleDateString(undefined, {
				year: "numeric",
				month: "short",
				day: "numeric",
			})
		: "";

// Rendering

function applyTheme(): void {
	const theme = state.settings.theme;
	if (theme === "auto") document.documentElement.removeAttribute("data-theme");
	else document.documentElement.setAttribute("data-theme", theme);
}

function render(): void {
	applyTheme();
	const counts = store.unreadCounts(state);
	const total = [...counts.values()].reduce((a, b) => a + b, 0);
	const feeds = $("#feeds");
	feeds.replaceChildren(
		feedButton(null, "All articles", total),
		...state.feeds.map((f) =>
			feedButton(f.url, f.title, counts.get(f.url) ?? 0, f.error),
		),
	);
	($("#unread-only") as HTMLInputElement).checked = state.settings.unreadOnly;
	const items = store.visibleItems(state, current.feed);
	const list = $("#items");
	list.replaceChildren(
		...items.map(([key, item]) => {
			const feed = state.feeds.find((f) => f.url === item.feed);
			const button = el(
				"button",
				{
					className: `item${item.read ? "" : " unread"}${key === current.item ? " current" : ""}`,
					type: "button",
				},
				el("span", { className: "item-title", textContent: item.title }),
				el("span", {
					className: "item-meta",
					textContent: [feed?.title, dateText(item.published)]
						.filter(Boolean)
						.join(" · "),
				}),
			);
			button.addEventListener("click", () => open(key));
			return el("li", {}, button);
		}),
	);
	if (!items.length)
		list.append(
			el("li", {
				className: "empty",
				textContent: state.feeds.length
					? "Nothing to read."
					: "Add a feed to start.",
			}),
		);
	renderReader();
}

function feedButton(
	url: string | null,
	title: string,
	unread: number,
	error: string | null = null,
): HTMLElement {
	const button = el(
		"button",
		{
			type: "button",
			className: `feed${current.feed === url ? " current" : ""}`,
			title: error ? `Last fetch failed: ${error}` : title,
		},
		el("span", {
			className: "feed-title",
			textContent: `${error ? "⚠ " : ""}${title}`,
		}),
		el("span", {
			className: "count",
			textContent: unread ? String(unread) : "",
		}),
	);
	button.addEventListener("click", () => {
		current = { feed: url, item: null };
		render();
	});
	return el("li", {}, button);
}

function renderReader(): void {
	const reader = $("#reader");
	const item = current.item ? state.items[current.item] : undefined;
	if (!item || !current.item) {
		reader.replaceChildren(
			el("p", { className: "empty", textContent: "Pick an article." }),
		);
		document.body.classList.remove("reading");
		return;
	}
	const key = current.item;
	const feed = state.feeds.find((f) => f.url === item.feed);
	const heading = el(
		"h1",
		{},
		item.link
			? el("a", {
					href: item.link,
					target: "_blank",
					rel: "noopener noreferrer",
					textContent: item.title,
				})
			: item.title,
	);
	const meta = el("p", {
		className: "meta",
		textContent: [feed?.title, item.author, dateText(item.published)]
			.filter(Boolean)
			.join(" · "),
	});
	const body = el("div", { className: "content" });
	body.innerHTML = sanitize(item.html, window, {
		base: item.link ?? item.feed,
		images: state.settings.images,
	});
	const actions = el("div", { className: "actions" });
	const back = el("button", {
		type: "button",
		className: "back",
		textContent: "← Back",
	});
	back.addEventListener("click", () => {
		current = { ...current, item: null };
		render();
	});
	const unread = el("button", { type: "button", textContent: "Mark unread" });
	unread.addEventListener("click", () =>
		update(store.markRead(state, key, false)),
	);
	actions.append(back, unread);
	const placeholders = body.querySelectorAll<HTMLImageElement>(
		`img.${IMAGE_PLACEHOLDER_CLASS}`,
	);
	if (placeholders.length) {
		const show = el("button", {
			type: "button",
			textContent: `Show ${placeholders.length} image${placeholders.length > 1 ? "s" : ""}`,
		});
		show.addEventListener("click", () => {
			for (const img of placeholders) {
				const src = img.dataset.freadSrc;
				if (src?.startsWith("http")) img.src = src;
				img.classList.remove(IMAGE_PLACEHOLDER_CLASS);
			}
			show.remove();
		});
		actions.append(show);
	}
	const summary = el("div", { className: "summary" });
	if (item.summary)
		summary.append(
			el("p", { textContent: item.summary.text }),
			el("p", {
				className: "meta",
				textContent: `Summary by ${item.summary.model}; it may be wrong.`,
			}),
		);
	if (state.settings.summaries.enabled) {
		const button = el("button", {
			type: "button",
			textContent: item.summary ? "Summarize again" : "Summarize",
		});
		button.addEventListener("click", () => summarizeItem(key, button));
		actions.append(button);
	}
	reader.replaceChildren(heading, meta, actions, summary, body);
	document.body.classList.add("reading");
}

function open(key: string): void {
	current = { ...current, item: key };
	update(store.markRead(state, key));
	render();
	$("#reader").scrollTop = 0;
}

async function summarizeItem(
	key: string,
	button: HTMLButtonElement,
): Promise<void> {
	const item = state.items[key];
	const { role, apiKey } = state.settings.summaries;
	if (!item || !apiKey) {
		status("Add an OpenRouter key in settings to summarize.");
		return;
	}
	button.disabled = true;
	status("Summarizing…");
	try {
		const text = await summarize(item, role, apiKey);
		update(
			store.setSummary(state, key, {
				text,
				model: ROLES[role] ?? role,
				at: new Date().toISOString(),
			}),
		);
		status("");
	} catch (error) {
		status(`Summary failed: ${(error as Error).message}`);
		button.disabled = false;
	}
}

// Fetching

async function refresh(urls = state.feeds.map((f) => f.url)): Promise<void> {
	if (!navigator.onLine) {
		status("Offline: showing saved articles.");
		return;
	}
	let done = 0;
	const queue = [...urls];
	const worker = async () => {
		for (let url = queue.shift(); url; url = queue.shift()) {
			try {
				const feed = await fetchFeed(url, state.settings.proxy);
				update(store.mergeFeed(state, url, feed, new Date().toISOString()));
			} catch (error) {
				update(store.feedFailed(state, url, (error as Error).message));
			}
			status(`Fetched ${++done} of ${urls.length} feeds.`);
		}
	};
	await Promise.all(Array.from({ length: Math.min(4, urls.length) }, worker));
	const failed = state.feeds.filter(
		(f) => urls.includes(f.url) && f.error,
	).length;
	status(
		failed
			? `${failed} feed${failed > 1 ? "s" : ""} failed; hover for why.`
			: "Up to date.",
	);
}

// Controls

function wire(): void {
	$("#add").addEventListener("submit", async (event) => {
		event.preventDefault();
		const input = $("#add-url") as HTMLInputElement;
		let url: string;
		try {
			url = normalizeFeedUrl(input.value);
		} catch (error) {
			status((error as Error).message);
			return;
		}
		input.value = "";
		update(
			store.addFeeds(state, [{ url, title: url, site: null, folder: null }]),
		);
		current = { feed: url, item: null };
		await refresh([url]);
	});
	$("#refresh").addEventListener("click", () => refresh());
	$("#mark-all").addEventListener("click", () =>
		update(store.markAllRead(state, current.feed)),
	);
	$("#unread-only").addEventListener("change", (event) =>
		update({
			...state,
			settings: {
				...state.settings,
				unreadOnly: (event.target as HTMLInputElement).checked,
			},
		}),
	);
	$("#import").addEventListener("change", async (event) => {
		const file = (event.target as HTMLInputElement).files?.[0];
		if (!file) return;
		try {
			const subs = parseOpml(await file.text());
			update(store.addFeeds(state, subs));
			status(`Imported ${subs.length} subscriptions.`);
			await refresh(subs.map((s) => s.url));
		} catch (error) {
			status(`Import failed: ${(error as Error).message}`);
		}
	});
	$("#export").addEventListener("click", () => {
		const blob = new Blob([toOpml(store.subscriptions(state))], {
			type: "text/x-opml",
		});
		const link = el("a", {
			href: URL.createObjectURL(blob),
			download: "fread-subscriptions.opml",
		});
		link.click();
		URL.revokeObjectURL(link.href);
	});
	const dialog = $("#settings") as HTMLDialogElement;
	$("#open-settings").addEventListener("click", () => {
		fillSettings();
		dialog.showModal();
	});
	$("#settings-form").addEventListener("submit", () => readSettings());
	const roles = $("#summary-role") as HTMLSelectElement;
	roles.replaceChildren(
		...Object.entries(ROLES).map(([role, model]) =>
			el("option", {
				value: role,
				textContent: `${role} (${model.replace(/^openrouter\//, "")})`,
			}),
		),
	);
	$("#remove-feed").addEventListener("click", () => {
		if (current.feed && confirm("Remove this feed and its saved articles?")) {
			const url = current.feed;
			current = { feed: null, item: null };
			update(store.removeFeed(state, url));
			dialog.close();
		}
	});
	window.addEventListener("online", () => refresh());
}

function fillSettings(): void {
	const s = state.settings;
	($("#theme") as HTMLSelectElement).value = s.theme;
	($("#proxy") as HTMLInputElement).value = s.proxy ?? "";
	($("#images") as HTMLInputElement).checked = s.images;
	($("#summaries") as HTMLInputElement).checked = s.summaries.enabled;
	($("#summary-role") as HTMLSelectElement).value = s.summaries.role;
	($("#api-key") as HTMLInputElement).value = s.summaries.apiKey ?? "";
	($("#remove-feed") as HTMLButtonElement).disabled = !current.feed;
}

function readSettings(): void {
	const proxy = ($("#proxy") as HTMLInputElement).value.trim();
	const apiKey = ($("#api-key") as HTMLInputElement).value.trim();
	update({
		...state,
		settings: {
			...state.settings,
			theme: ($("#theme") as HTMLSelectElement).value as store.Theme,
			proxy: proxy || null,
			images: ($("#images") as HTMLInputElement).checked,
			summaries: {
				enabled: ($("#summaries") as HTMLInputElement).checked,
				role: ($("#summary-role") as HTMLSelectElement).value,
				apiKey: apiKey || null,
			},
		},
	});
}

async function main(): Promise<void> {
	wire();
	state = await load();
	render();
	if ("serviceWorker" in navigator)
		navigator.serviceWorker.register("sw.js").catch(() => {});
	await refresh();
}

main();
