import { expect, test } from "bun:test";
import { fetchFeed, normalizeFeedUrl, requestUrl } from "./fetch";

test("requests the feed directly unless a proxy is set", () => {
	expect(requestUrl("https://a.example/feed?x=1", null)).toBe(
		"https://a.example/feed?x=1",
	);
	expect(
		requestUrl("https://a.example/feed?x=1", "https://p.example/?url={url}"),
	).toBe("https://p.example/?url=https%3A%2F%2Fa.example%2Ffeed%3Fx%3D1");
	expect(requestUrl("https://a.example/f", "https://p.example/raw/")).toBe(
		"https://p.example/raw/https%3A%2F%2Fa.example%2Ff",
	);
});

test("feed URLs must be http or https", () => {
	expect(normalizeFeedUrl(" example.org/feed ")).toBe(
		"https://example.org/feed",
	);
	expect(() => normalizeFeedUrl("javascript:alert(1)")).toThrow();
	expect(() => normalizeFeedUrl("file:///etc/passwd")).toThrow();
});

test("fetches without cookies or referrer and parses", async () => {
	const calls: [string, RequestInit | undefined][] = [];
	const fake = (async (url: string, init?: RequestInit) => {
		calls.push([url, init]);
		return new Response(
			'<rss version="2.0"><channel><title>T</title><item><title>a</title><guid>1</guid></item></channel></rss>',
		);
	}) as unknown as typeof fetch;
	const feed = await fetchFeed("https://a.example/feed", null, fake);
	expect(feed.items[0]?.id).toBe("1");
	expect(calls[0]?.[0]).toBe("https://a.example/feed");
	expect(calls[0]?.[1]).toMatchObject({
		credentials: "omit",
		referrerPolicy: "no-referrer",
	});
});

test("explains failures", async () => {
	const down = (async () => {
		throw new TypeError("Failed to fetch");
	}) as unknown as typeof fetch;
	expect(fetchFeed("https://a.example/feed", null, down)).rejects.toThrow(
		"CORS",
	);
	const missing = (async () =>
		new Response("nope", { status: 404 })) as unknown as typeof fetch;
	expect(fetchFeed("https://a.example/feed", null, missing)).rejects.toThrow(
		"HTTP 404",
	);
});
