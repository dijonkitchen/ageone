import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { OpmlError, parseOpml, toOpml } from "./opml";

const fixture = (name: string) =>
	readFileSync(join(import.meta.dir, "../test/fixtures", name), "utf8");

test("reads Feedly's export, folders included", () => {
	const subs = parseOpml(fixture("feedly.opml"));
	expect(subs).toEqual([
		{
			url: "https://lwn.net/headlines/rss",
			title: "LWN.net",
			site: "https://lwn.net",
			folder: "Tech",
		},
		{
			url: "https://blog.rust-lang.org/feed.xml",
			title: "Rust Blog",
			site: "https://blog.rust-lang.org/",
			folder: "Tech",
		},
		{
			url: "https://xkcd.com/atom.xml",
			title: "xkcd.com",
			site: "https://xkcd.com/",
			folder: "Comics",
		},
	]);
});

test("reads NetNewsWire's export: top-level feeds, escaped names, and duplicates once", () => {
	const subs = parseOpml(fixture("netnewswire.opml"));
	expect(subs.map((s) => [s.title, s.folder])).toEqual([
		["Debian News", null],
		["Planet Debian", "News & Views"],
		["LWN.net", "News & Views"],
	]);
});

test("round-trips: another reader's export, through ours, reads back the same", () => {
	for (const name of ["feedly.opml", "netnewswire.opml"]) {
		const subs = parseOpml(fixture(name));
		const ours = toOpml(subs);
		expect(parseOpml(ours)).toEqual(subs);
		// What other readers look for: OPML 2.0 with type="rss" outlines carrying xmlUrl.
		expect(ours).toContain('<opml version="2.0">');
		expect(ours.match(/<outline type="rss" [^>]*xmlUrl="/g)).toHaveLength(
			subs.length,
		);
	}
});

test("escapes what it writes", () => {
	const ours = toOpml([
		{
			url: "https://e.example/?a=1&b=2",
			title: 'Say "hi" <now>',
			site: null,
			folder: "A & B",
		},
	]);
	expect(ours).toContain('xmlUrl="https://e.example/?a=1&amp;b=2"');
	expect(parseOpml(ours)[0]).toEqual({
		url: "https://e.example/?a=1&b=2",
		title: 'Say "hi" <now>',
		site: null,
		folder: "A & B",
	});
});

test("rejects what isn't OPML", () => {
	expect(() => parseOpml("<rss/>")).toThrow(OpmlError);
	expect(() => parseOpml("<opml version='2.0'><head/></opml>")).toThrow(
		OpmlError,
	);
});
