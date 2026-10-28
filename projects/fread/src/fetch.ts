// Fetch a feed straight from its site, or through a CORS proxy the user chose (off by default).

import { type Feed, parseFeed } from "./feed";

/** The URL to request: the feed itself, or the proxy template with {url} replaced (or the URL appended). */
export function requestUrl(feedUrl: string, proxy: string | null): string {
	if (!proxy) return feedUrl;
	const encoded = encodeURIComponent(feedUrl);
	return proxy.includes("{url}")
		? proxy.replaceAll("{url}", encoded)
		: `${proxy}${encoded}`;
}

export function normalizeFeedUrl(input: string): string {
	const trimmed = input.trim();
	const url = new URL(
		/^[a-z][a-z0-9+.-]*:/i.test(trimmed) ? trimmed : `https://${trimmed}`,
	);
	if (url.protocol !== "https:" && url.protocol !== "http:")
		throw new Error("feeds must be http or https URLs");
	return url.href;
}

export async function fetchFeed(
	url: string,
	proxy: string | null,
	fetcher: typeof fetch = fetch,
): Promise<Feed> {
	let response: Response;
	try {
		response = await fetcher(requestUrl(url, proxy), {
			credentials: "omit",
			referrerPolicy: "no-referrer",
			cache: "no-cache",
			headers: {
				accept:
					"application/atom+xml, application/rss+xml, application/rdf+xml, application/xml, text/xml;q=0.9, */*;q=0.1",
			},
		});
	} catch {
		throw new Error(
			proxy
				? "the proxy didn't answer"
				: "the site didn't answer or doesn't allow browser readers (CORS); a proxy in settings can help",
		);
	}
	if (!response.ok) throw new Error(`HTTP ${response.status}`);
	return parseFeed(await response.text(), url);
}
