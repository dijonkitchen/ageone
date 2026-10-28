import { expect, test } from "bun:test";
import type { Feed } from "./feed";
import * as store from "./store";

const URL_A = "https://a.example/feed";
const URL_B = "https://b.example/feed";
const feed = (ids: string[], title = "A feed"): Feed => ({
	format: "rss2",
	title,
	link: "https://a.example/",
	items: ids.map((id, n) => ({
		id,
		title: `Post ${id}`,
		link: null,
		published: `2024-01-${String(10 + n).padStart(2, "0")}T00:00:00.000Z`,
		author: null,
		html: `<p>${id}</p>`,
	})),
});
const sub = (url: string) => ({ url, title: url, site: null, folder: null });

function withTwoFeeds() {
	let s = store.addFeeds(store.emptyState(), [
		sub(URL_A),
		sub(URL_B),
		sub(URL_A),
	]);
	s = store.mergeFeed(
		s,
		URL_A,
		feed(["1", "2", "3"]),
		"2024-02-01T00:00:00.000Z",
	);
	return store.mergeFeed(
		s,
		URL_B,
		feed(["x"], "B feed"),
		"2024-02-01T00:00:00.000Z",
	);
}

test("adding feeds skips duplicates and takes the feed's title once fetched", () => {
	const s = withTwoFeeds();
	expect(s.feeds.map((f) => [f.url, f.title, f.site])).toEqual([
		[URL_A, "A feed", "https://a.example/"],
		[URL_B, "B feed", "https://a.example/"],
	]);
});

test("unread counts, marking read, and the unread-only filter", () => {
	let s = withTwoFeeds();
	expect(Object.fromEntries(store.unreadCounts(s))).toEqual({
		[URL_A]: 3,
		[URL_B]: 1,
	});
	s = store.markRead(s, store.itemKey(URL_A, "2"));
	expect(store.unreadCounts(s).get(URL_A)).toBe(2);
	expect(store.visibleItems(s, URL_A, true).map(([, i]) => i.id)).toEqual([
		"3",
		"1",
	]);
	// Newest first; "1" and "x" share a date, so their ids break the tie.
	expect(store.visibleItems(s, null, false).map(([, i]) => i.id)).toEqual([
		"3",
		"2",
		"1",
		"x",
	]);
	s = store.markAllRead(s, URL_A);
	expect(Object.fromEntries(store.unreadCounts(s))).toEqual({
		[URL_A]: 0,
		[URL_B]: 1,
	});
});

test("refetching keeps read flags and summaries, and adds new items unread", () => {
	let s = withTwoFeeds();
	const key = store.itemKey(URL_A, "1");
	s = store.markRead(s, key);
	s = store.setSummary(s, key, { text: "short", model: "m", at: "t" });
	s = store.mergeFeed(s, URL_A, feed(["1", "4"]), "2024-03-01T00:00:00.000Z");
	expect(s.items[key]).toMatchObject({
		read: true,
		summary: { text: "short" },
		seenAt: "2024-02-01T00:00:00.000Z",
	});
	expect(s.items[store.itemKey(URL_A, "4")]?.read).toBe(false);
	expect(store.unreadCounts(s).get(URL_A)).toBe(3); // 2, 3, 4
});

test("old read items beyond the cap are dropped, unread ones never", () => {
	const ids = Array.from({ length: store.MAX_ITEMS_PER_FEED + 5 }, (_, n) =>
		String(n).padStart(4, "0"),
	);
	let s = store.addFeeds(store.emptyState(), [sub(URL_A)]);
	s = store.mergeFeed(
		s,
		URL_A,
		{
			...feed([]),
			items: feed(ids).items.map((item) => ({
				...item,
				published: `2024-01-01T00:00:00.${item.id.slice(1)}Z`,
			})),
		},
		"now",
	);
	s = store.markAllRead(s);
	s = store.mergeFeed(s, URL_A, feed([]), "later");
	expect(Object.keys(s.items)).toHaveLength(store.MAX_ITEMS_PER_FEED);
	expect(s.items[store.itemKey(URL_A, "0000")]).toBeUndefined();
});

test("removing a feed removes its items", () => {
	const s = store.removeFeed(withTwoFeeds(), URL_A);
	expect(s.feeds.map((f) => f.url)).toEqual([URL_B]);
	expect(Object.values(s.items).every((i) => i.feed === URL_B)).toBe(true);
});

test("failures are recorded per feed and cleared by the next success", () => {
	let s = store.feedFailed(withTwoFeeds(), URL_A, "HTTP 500");
	expect(s.feeds[0]?.error).toBe("HTTP 500");
	s = store.mergeFeed(s, URL_A, feed(["1"]), "later");
	expect(s.feeds[0]?.error).toBeNull();
});

test("state survives a save and load, and bad stored data falls back to defaults", () => {
	const s = store.markRead(withTwoFeeds(), store.itemKey(URL_B, "x"));
	expect(store.deserialize(store.serialize(s))).toEqual(s);
	expect(store.deserialize(null)).toEqual(store.emptyState());
	expect(store.deserialize("{not json")).toEqual(store.emptyState());
	expect(store.deserialize('{"version":2}')).toEqual(store.emptyState());
	const partial = store.deserialize(
		'{"version":1,"feeds":[{"url":"u"},{"nope":1}],"settings":{"theme":"dark","summaries":{"enabled":true}}}',
	);
	expect(partial.feeds).toHaveLength(1);
	expect(partial.settings).toMatchObject({
		theme: "dark",
		proxy: null,
		images: false,
		summaries: { enabled: true, role: "cheap", apiKey: null },
	});
});

test("privacy defaults: no proxy, no images, no summaries", () => {
	expect(store.defaultSettings()).toMatchObject({
		proxy: null,
		images: false,
		summaries: { enabled: false, apiKey: null },
	});
});
