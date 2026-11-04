import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { FeedError, parseFeed } from "./feed";

const fixture = (name: string) =>
	readFileSync(join(import.meta.dir, "../test/fixtures", name), "utf8");

// Real feeds, recorded 2026-10-23 (big ones trimmed to their first items).
describe("real samples of each format", () => {
	test("Atom: xkcd", () => {
		const feed = parseFeed(
			fixture("xkcd.atom.xml"),
			"https://xkcd.com/atom.xml",
		);
		expect(feed).toMatchObject({
			format: "atom",
			title: "xkcd.com",
			link: "https://xkcd.com/",
		});
		expect(feed.items).toHaveLength(4);
		expect(feed.items[0]).toMatchObject({
			id: "https://xkcd.com/3314/",
			title: "Vulnerability",
			link: "https://xkcd.com/3314/",
			published: "2026-10-21T00:00:00.000Z",
		});
		expect(feed.items[0]?.html).toStartWith(
			'<img src="https://imgs.xkcd.com/comics/vulnerability.png"',
		);
	});

	test("Atom: Rust blog, with authors and html content", () => {
		const feed = parseFeed(
			fixture("rust-blog.atom.xml"),
			"https://blog.rust-lang.org/feed.xml",
		);
		expect(feed.title).toBe("Rust Blog");
		expect(feed.items.map((i) => i.title)).toEqual([
			"Announcing rustup 1.29.2",
			"Announcing Rust 1.99.1",
		]);
		expect(feed.items[0]?.author).toBe("The Rustup Team");
		expect(feed.items[0]?.html).toStartWith(
			"<p>The rustup team is happy to announce",
		);
	});

	test("RSS 2.0: xkcd and LWN", () => {
		const xkcd = parseFeed(fixture("xkcd.rss.xml"), "https://xkcd.com/rss.xml");
		expect(xkcd).toMatchObject({
			format: "rss2",
			title: "xkcd.com",
			link: "https://xkcd.com/",
		});
		expect(xkcd.items[0]).toMatchObject({
			title: "Vulnerability",
			link: "https://xkcd.com/3314/",
			published: "2026-10-21T04:00:00.000Z",
		});
		const lwn = parseFeed(
			fixture("lwn.rss.xml"),
			"https://lwn.net/headlines/rss",
		);
		expect(lwn.items).toHaveLength(3);
		expect(lwn.items[0]).toMatchObject({
			id: "https://lwn.net/Articles/1102061/",
			title: "[$] The end of __get_user() and __put_user()",
			author: "corbet",
			published: "2026-10-22T16:25:50.000Z",
		});
	});

	test("RSS 1.0 (RDF): Debian News and Planet Debian", () => {
		const news = parseFeed(
			fixture("debian-news.rdf"),
			"https://www.debian.org/News/news",
		);
		expect(news).toMatchObject({
			format: "rss1",
			title: "Debian News",
			link: "https://www.debian.org/News/",
		});
		expect(news.items).toHaveLength(6);
		expect(news.items[0]).toMatchObject({
			id: "https://www.debian.org/News/2026/20260912",
			title: "Updated Debian 13: 13.7 released",
			published: "2026-09-12T00:00:00.000Z",
		});
		// Escaped markup in the description comes back as HTML.
		expect(news.items[0]?.html).toContain("<q>trixie</q>");
		const planet = parseFeed(
			fixture("planet-debian.rdf"),
			"https://planet.debian.org/rss10.xml",
		);
		expect(planet.items[0]).toMatchObject({
			author: "Steinar H. Gunderson",
			published: "2026-10-21T21:30:20.000Z",
		});
		expect(planet.items[0]?.html).toStartWith("<p>As promised");
	});
});

describe("edge cases", () => {
	test("Atom text, xhtml, relative links, and xml:base", () => {
		const feed = parseFeed(
			`<feed xmlns="http://www.w3.org/2005/Atom" xml:base="https://example.org/blog/">
				<title type="text">AT&amp;T &lt;news&gt;</title><link href="/"/>
				<entry><id>urn:1</id><title type="html">&lt;b&gt;Bold&lt;/b&gt; move</title><link rel="alternate" href="posts/1"/>
					<updated>2024-01-02T03:04:05+01:00</updated>
					<content type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml"><p>Hi <a href="x">there</a> &amp; you</p></div></content></entry>
				<entry><id>urn:2</id><title>Plain</title><summary>1 &lt; 2</summary></entry>
			</feed>`,
			"https://example.org/feed.atom",
		);
		expect(feed.title).toBe("AT&T <news>");
		expect(feed.link).toBe("https://example.org/");
		expect(feed.items[0]).toMatchObject({
			title: "Bold move",
			link: "https://example.org/blog/posts/1",
			published: "2024-01-02T02:04:05.000Z",
		});
		expect(feed.items[0]?.html).toBe(
			'<p>Hi <a href="x">there</a> &amp; you</p>',
		);
		expect(feed.items[1]?.html).toBe("1 &lt; 2");
	});

	test("RSS with CDATA, HTML entities, no guid, a stray end tag, and a bad date", () => {
		const feed = parseFeed(
			`<?xml version="1.0"?><!DOCTYPE rss [<!ENTITY x "y">]><rss version="2.0"><channel><title>Caf&eacute;&nbsp;news</title><link>https://cafe.example/</link>
				<item><title>One</title><link>/one</link><description><![CDATA[<p>Hello <b>world</b></p>]]></description><pubDate>not a date</pubDate></item></b>
				<item><title>Two &mdash; more</title><description>no link</description></item>
			</channel></rss>`,
			"https://cafe.example/rss",
		);
		// Unknown undeclared entities stay as written; whitespace, &nbsp; included, collapses in titles.
		expect(feed.title).toBe("Caf&eacute; news");
		expect(feed.items[0]).toMatchObject({
			id: "https://cafe.example/one",
			link: "https://cafe.example/one",
			published: null,
			html: "<p>Hello <b>world</b></p>",
		});
		expect(feed.items[1]?.title).toBe("Two — more");
		expect(feed.items[1]?.id).toStartWith("fread:");
		// The fallback id is stable across fetches.
		const again = parseFeed(
			"<rss><channel><item><title>Two &#8212; more</title><description>no link</description></item></channel></rss>",
		);
		expect(again.items[0]?.id).toBe(feed.items[1]?.id as string);
	});

	test("not a feed", () => {
		expect(() => parseFeed("<html><body>hi</body></html>")).toThrow(FeedError);
		expect(() => parseFeed("plain text")).toThrow(FeedError);
	});
});
