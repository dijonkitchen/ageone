// The reader's state and every change to it, as pure functions; app.ts persists the result in IndexedDB.

import type { Feed, Item } from "./feed";
import type { Subscription } from "./opml";

export type Theme = "auto" | "light" | "dark";

export interface Settings {
	theme: Theme;
	unreadOnly: boolean;
	proxy: string | null; // CORS proxy template, e.g. "https://proxy.example/?url={url}"; off by default
	images: boolean; // load images in articles (contacts their hosts)
	summaries: { enabled: boolean; role: string; apiKey: string | null };
}

export interface FeedState extends Subscription {
	fetchedAt: string | null;
	error: string | null;
}

export interface StoredItem extends Item {
	feed: string; // the feed's URL
	read: boolean;
	seenAt: string;
	summary?: { text: string; model: string; at: string };
}

export interface State {
	version: 1;
	feeds: FeedState[];
	items: Record<string, StoredItem>;
	settings: Settings;
}

export const MAX_ITEMS_PER_FEED = 500;

export const defaultSettings = (): Settings => ({
	theme: "auto",
	unreadOnly: false,
	proxy: null,
	images: false,
	summaries: { enabled: false, role: "cheap", apiKey: null },
});

export const emptyState = (): State => ({
	version: 1,
	feeds: [],
	items: {},
	settings: defaultSettings(),
});

export const itemKey = (feed: string, id: string): string => `${feed}\n${id}`;

export function addFeeds(state: State, subs: Subscription[]): State {
	const known = new Set(state.feeds.map((f) => f.url));
	const added = subs
		.filter((s) => !known.has(s.url) && known.add(s.url))
		.map((s): FeedState => ({ ...s, fetchedAt: null, error: null }));
	return added.length ? { ...state, feeds: [...state.feeds, ...added] } : state;
}

export function removeFeed(state: State, url: string): State {
	const items = Object.fromEntries(
		Object.entries(state.items).filter(([, item]) => item.feed !== url),
	);
	return { ...state, feeds: state.feeds.filter((f) => f.url !== url), items };
}

const newest = (a: StoredItem, b: StoredItem) =>
	(b.published ?? b.seenAt).localeCompare(a.published ?? a.seenAt) ||
	a.id.localeCompare(b.id);

/** Fold a fetched feed in: new items arrive unread, known ones keep their read flag and summary. */
export function mergeFeed(
	state: State,
	url: string,
	feed: Feed,
	now: string,
): State {
	const items = { ...state.items };
	for (const item of feed.items) {
		const key = itemKey(url, item.id);
		const old = items[key];
		items[key] = {
			...item,
			feed: url,
			read: old?.read ?? false,
			seenAt: old?.seenAt ?? now,
			summary: old?.summary,
		};
	}
	// Keep each feed's newest items, plus every unread one.
	const mine = Object.entries(items)
		.filter(([, i]) => i.feed === url)
		.sort(([, a], [, b]) => newest(a, b));
	for (const [key, item] of mine.slice(MAX_ITEMS_PER_FEED))
		if (item.read) delete items[key];
	const feeds = state.feeds.map((f) =>
		f.url === url
			? {
					...f,
					title: f.title === f.url ? feed.title : f.title,
					site: f.site ?? feed.link,
					fetchedAt: now,
					error: null,
				}
			: f,
	);
	return { ...state, feeds, items };
}

export function feedFailed(state: State, url: string, error: string): State {
	return {
		...state,
		feeds: state.feeds.map((f) => (f.url === url ? { ...f, error } : f)),
	};
}

export function markRead(state: State, key: string, read = true): State {
	const item = state.items[key];
	if (!item || item.read === read) return state;
	return { ...state, items: { ...state.items, [key]: { ...item, read } } };
}

export function markAllRead(state: State, feed: string | null = null): State {
	const items = Object.fromEntries(
		Object.entries(state.items).map(([k, i]) => [
			k,
			feed === null || i.feed === feed ? { ...i, read: true } : i,
		]),
	);
	return { ...state, items };
}

export function setSummary(
	state: State,
	key: string,
	summary: StoredItem["summary"],
): State {
	const item = state.items[key];
	return item
		? { ...state, items: { ...state.items, [key]: { ...item, summary } } }
		: state;
}

export function unreadCounts(state: State): Map<string, number> {
	const counts = new Map(state.feeds.map((f) => [f.url, 0]));
	for (const item of Object.values(state.items))
		if (!item.read) counts.set(item.feed, (counts.get(item.feed) ?? 0) + 1);
	return counts;
}

/** Items to list, newest first: one feed or all, unread only or not. */
export function visibleItems(
	state: State,
	feed: string | null,
	unreadOnly = state.settings.unreadOnly,
): [string, StoredItem][] {
	return Object.entries(state.items)
		.filter(
			([, i]) => (feed === null || i.feed === feed) && (!unreadOnly || !i.read),
		)
		.sort(([, a], [, b]) => newest(a, b));
}

export const subscriptions = (state: State): Subscription[] =>
	state.feeds.map(({ url, title, site, folder }) => ({
		url,
		title,
		site,
		folder,
	}));

export const serialize = (state: State): string => JSON.stringify(state);

/** Read stored state back, falling back to defaults for anything missing or malformed. */
export function deserialize(json: string | null): State {
	if (!json) return emptyState();
	let raw: unknown;
	try {
		raw = JSON.parse(json);
	} catch {
		return emptyState();
	}
	if (!raw || typeof raw !== "object" || (raw as State).version !== 1)
		return emptyState();
	const s = raw as Partial<State>;
	const defaults = defaultSettings();
	const settings = {
		...defaults,
		...(s.settings ?? {}),
		summaries: { ...defaults.summaries, ...(s.settings?.summaries ?? {}) },
	};
	return {
		version: 1,
		feeds: Array.isArray(s.feeds)
			? s.feeds.filter((f) => typeof f?.url === "string")
			: [],
		items: s.items && typeof s.items === "object" ? s.items : {},
		settings,
	};
}
