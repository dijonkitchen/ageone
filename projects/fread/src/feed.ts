// RSS 2.0, RSS 1.0 (RDF), and Atom to one shape. Pure: text in, data out; HTML stays unsanitized here
// and is sanitized only when shown (sanitize.ts).

import {
	child,
	children,
	decodeEntities,
	elements,
	escapeText,
	localName,
	parseXml,
	serialize,
	textOf,
	type XmlElement,
} from "./xml";

export type FeedFormat = "rss2" | "rss1" | "atom";

export interface Item {
	id: string;
	title: string;
	link: string | null;
	published: string | null; // ISO 8601
	author: string | null;
	html: string; // content or summary, as HTML (unsanitized)
}

export interface Feed {
	format: FeedFormat;
	title: string;
	link: string | null;
	items: Item[];
}

export class FeedError extends Error {}

const clean = (s: string) => s.replace(/\s+/g, " ").trim();

function resolve(
	href: string | undefined | null,
	base: string | null,
): string | null {
	const value = href?.trim();
	if (!value) return null;
	try {
		return new URL(value, base ?? undefined).href;
	} catch {
		return null;
	}
}

function date(value: string | undefined): string | null {
	const text = value?.trim();
	if (!text) return null;
	const ms = Date.parse(text);
	return Number.isNaN(ms) ? null : new Date(ms).toISOString();
}

// HTML element names, so tags like <a class="u-url p-name"> come out of titles but text like
// "AT&T <news>" stays.
const HTML_TAG = new RegExp(
	`<!--[\\s\\S]*?-->|</?(?:${[
		"a abbr acronym address area article aside audio b bdi bdo big blink blockquote body br",
		"button canvas caption center cite code col colgroup data datalist dd del details dfn",
		"dialog dir div dl dt em embed fieldset figcaption figure font footer form frame frameset",
		"h1 h2 h3 h4 h5 h6 head header hgroup hr html i iframe img input ins kbd label legend li",
		"link main map mark marquee menu meta meter nav nobr noscript object ol optgroup option",
		"output p param picture pre progress q rp rt ruby s samp script section select slot small",
		"source span strike strong style sub summary sup svg table tbody td template textarea",
		"tfoot th thead time title tr track tt u ul var video wbr",
	]
		.join(" ")
		.replace(/ /g, "|")})(?=[\\s/>])[^>]*>`,
	"gi",
);

/**
 * Plain text of a title that may hold markup, escaped once or more: decode and strip every HTML tag
 * until nothing changes.
 */
function plain(text: string): string {
	let current = text;
	for (let i = 0; i < 4; i++) {
		const next = decodeEntities(current.replace(HTML_TAG, " "));
		if (next === current) break;
		current = next;
	}
	return clean(current.replace(HTML_TAG, " "));
}

function atomTitle(node: XmlElement | undefined): string {
	if (!node) return "";
	if (node.attrs.type === "xhtml") return clean(textOf(node));
	// Feeds often put HTML in type="text" titles, so they get the same treatment.
	return plain(textOf(node));
}

const escapeHtml = (text: string) => escapeText(text).replace(/\n/g, "<br>");

/** A stable id when a feed gives none. */
function fallbackId(...parts: (string | null)[]): string {
	let h = 0x811c9dc5;
	for (const ch of parts.join("\u0000")) {
		h ^= ch.codePointAt(0) ?? 0;
		h = Math.imul(h, 0x01000193) >>> 0;
	}
	return `fread:${h.toString(16)}`;
}

export function parseFeed(xml: string, url: string | null = null): Feed {
	const doc = parseXml(xml);
	const root = elements(doc)[0];
	if (!root) throw new FeedError("not XML");
	switch (localName(root.name)) {
		case "rss":
			return rss(root, child(root, "channel"), "rss2", url);
		case "RDF":
			return rss(root, child(root, "channel"), "rss1", url);
		case "feed":
			return atom(root, url);
		default:
			throw new FeedError(`not a feed: <${root.name}>`);
	}
}

function rss(
	root: XmlElement,
	channel: XmlElement | undefined,
	format: FeedFormat,
	url: string | null,
): Feed {
	if (!channel) throw new FeedError("RSS without a channel");
	const link = resolve(textOf(child(channel, "link")), url);
	// RSS 2.0 items sit inside the channel; RSS 1.0 items are the channel's siblings.
	const nodes =
		format === "rss2" ? children(channel, "item") : children(root, "item");
	const items = nodes.map((node): Item => {
		const itemLink = resolve(textOf(child(node, "link")), link ?? url);
		const guid =
			clean(textOf(child(node, "guid"))) || node.attrs["rdf:about"] || null;
		const title = plain(textOf(child(node, "title")));
		const published = date(
			textOf(child(node, "pubDate")) || textOf(child(node, "dc:date")),
		);
		const html =
			textOf(child(node, "content:encoded")) ||
			textOf(child(node, "description"));
		return {
			id: guid ?? itemLink ?? fallbackId(title, published, html.slice(0, 200)),
			title: title || "(untitled)",
			link: itemLink,
			published,
			author:
				clean(
					textOf(child(node, "dc:creator")) || textOf(child(node, "author")),
				) || null,
			html: html.trim(),
		};
	});
	return {
		format,
		title:
			plain(textOf(child(channel, "title"))) || link || url || "Untitled feed",
		link,
		items,
	};
}

function atomLink(node: XmlElement, base: string | null): string | null {
	const links = children(node, "link");
	const alternate =
		links.find((l) => (l.attrs.rel ?? "alternate") === "alternate") ?? links[0];
	return resolve(alternate?.attrs.href, base);
}

/** Atom text constructs: text, html, or inline xhtml, returned as HTML. */
function atomHtml(node: XmlElement | undefined): string {
	if (!node) return "";
	const type = node.attrs.type ?? "text";
	if (type === "xhtml") {
		const div = elements(node).find((e) => localName(e.name) === "div");
		return (div ? div.children : node.children).map(serialize).join("").trim();
	}
	if (type === "html" || type === "text/html") return textOf(node).trim();
	return escapeHtml(textOf(node).trim());
}

function atom(root: XmlElement, url: string | null): Feed {
	const base = resolve(root.attrs["xml:base"], url) ?? url;
	const link = atomLink(root, base);
	const items = children(root, "entry").map((node): Item => {
		const entryBase = resolve(node.attrs["xml:base"], base) ?? base;
		const itemLink = atomLink(node, entryBase);
		const title = atomTitle(child(node, "title"));
		const published = date(
			textOf(child(node, "published")) || textOf(child(node, "updated")),
		);
		const content = child(node, "content");
		const html = content?.attrs.src
			? ""
			: atomHtml(content) || atomHtml(child(node, "summary"));
		return {
			id:
				clean(textOf(child(node, "id"))) ||
				itemLink ||
				fallbackId(title, published),
			title: title || "(untitled)",
			link: itemLink ?? resolve(content?.attrs.src, entryBase),
			published,
			author: clean(textOf(child(child(node, "author"), "name"))) || null,
			html,
		};
	});
	const title = atomTitle(child(root, "title"));
	return {
		format: "atom",
		title: title || link || url || "Untitled feed",
		link,
		items,
	};
}
