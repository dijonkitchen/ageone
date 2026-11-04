// OPML 1.0 and 2.0 subscription lists, as other readers export them: nested outlines are folders.

import {
	children,
	escapeAttr,
	localName,
	parseXml,
	type XmlElement,
} from "./xml";

export interface Subscription {
	url: string; // xmlUrl
	title: string;
	site: string | null; // htmlUrl
	folder: string | null;
}

export class OpmlError extends Error {}

export function parseOpml(xml: string): Subscription[] {
	const root = parseXml(xml).children.find(
		(c): c is XmlElement =>
			typeof c !== "string" && localName(c.name) === "opml",
	);
	if (!root) throw new OpmlError("not an OPML file");
	const body = children(root, "body")[0];
	if (!body) throw new OpmlError("OPML without a body");
	const out: Subscription[] = [];
	const seen = new Set<string>();
	const walk = (node: XmlElement, folder: string | null) => {
		for (const outline of children(node, "outline")) {
			const url = outline.attrs.xmlUrl ?? outline.attrs.xmlurl;
			const title = (outline.attrs.title ?? outline.attrs.text ?? "").trim();
			if (url) {
				if (!seen.has(url))
					out.push({
						url,
						title: title || url,
						site: outline.attrs.htmlUrl ?? null,
						folder,
					});
				seen.add(url);
			}
			walk(outline, url ? folder : title || folder);
		}
	};
	walk(body, null);
	return out;
}

export function toOpml(
	subscriptions: Subscription[],
	title = "fread subscriptions",
): string {
	const line = (s: Subscription, indent: string) =>
		`${indent}<outline type="rss" text="${escapeAttr(s.title)}" title="${escapeAttr(s.title)}" xmlUrl="${escapeAttr(s.url)}"${
			s.site ? ` htmlUrl="${escapeAttr(s.site)}"` : ""
		}/>`;
	const folders = new Map<string | null, Subscription[]>();
	for (const s of subscriptions)
		folders.set(s.folder, [...(folders.get(s.folder) ?? []), s]);
	const body: string[] = [];
	for (const [folder, subs] of folders) {
		if (folder === null) body.push(...subs.map((s) => line(s, "    ")));
		else {
			body.push(
				`    <outline text="${escapeAttr(folder)}" title="${escapeAttr(folder)}">`,
			);
			body.push(...subs.map((s) => line(s, "      ")));
			body.push("    </outline>");
		}
	}
	return `<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head>
    <title>${escapeAttr(title)}</title>
  </head>
  <body>
${body.join("\n")}
  </body>
</opml>
`;
}
