// A small, lenient XML parser for feeds and OPML: pure, no DOM, so it runs and tests anywhere.
// Feeds in the wild break XML rules (HTML entities, stray end tags), so it recovers instead of failing.

export interface XmlElement {
	name: string; // qualified name as written, e.g. "dc:date"
	attrs: Record<string, string>;
	children: XmlNode[];
}
export type XmlNode = XmlElement | string;

const XML_ENTITIES: Record<string, string> = {
	lt: "<",
	gt: ">",
	amp: "&",
	quot: '"',
	apos: "'",
};
// HTML entities feeds often use without declaring them.
const HTML_ENTITIES: Record<string, string> = {
	nbsp: " ",
	copy: "©",
	reg: "®",
	trade: "™",
	mdash: "—",
	ndash: "–",
	hellip: "…",
	lsquo: "‘",
	rsquo: "’",
	ldquo: "“",
	rdquo: "”",
	laquo: "«",
	raquo: "»",
	middot: "·",
	bull: "•",
	euro: "€",
	pound: "£",
	yen: "¥",
	cent: "¢",
	deg: "°",
	times: "×",
};

export function decodeEntities(text: string): string {
	return text.replace(
		/&(#x[0-9a-fA-F]+|#[0-9]+|[a-zA-Z][a-zA-Z0-9]*);/g,
		(whole, ref: string) => {
			if (ref[0] === "#") {
				const code =
					ref[1] === "x" || ref[1] === "X"
						? Number.parseInt(ref.slice(2), 16)
						: Number.parseInt(ref.slice(1), 10);
				return code > 0 &&
					code <= 0x10ffff &&
					!(code >= 0xd800 && code <= 0xdfff)
					? String.fromCodePoint(code)
					: "�";
			}
			return XML_ENTITIES[ref] ?? HTML_ENTITIES[ref] ?? whole;
		},
	);
}

const NAME = /[^\s/>=]+/y;
const ATTR = /\s*([^\s/>=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/y;

export function parseXml(source: string): XmlElement {
	const root: XmlElement = { name: "#document", attrs: {}, children: [] };
	const stack: XmlElement[] = [root];
	const top = () => stack[stack.length - 1] as XmlElement;
	let i = 0;
	const text = (raw: string) => {
		if (raw) top().children.push(decodeEntities(raw));
	};
	while (i < source.length) {
		const lt = source.indexOf("<", i);
		if (lt < 0) {
			text(source.slice(i));
			break;
		}
		text(source.slice(i, lt));
		if (source.startsWith("<!--", lt)) {
			const end = source.indexOf("-->", lt + 4);
			i = end < 0 ? source.length : end + 3;
		} else if (source.startsWith("<![CDATA[", lt)) {
			const end = source.indexOf("]]>", lt + 9);
			top().children.push(source.slice(lt + 9, end < 0 ? source.length : end));
			i = end < 0 ? source.length : end + 3;
		} else if (source.startsWith("<?", lt)) {
			const end = source.indexOf("?>", lt + 2);
			i = end < 0 ? source.length : end + 2;
		} else if (source.startsWith("<!", lt)) {
			// DOCTYPE, possibly with an internal subset in brackets.
			let depth = 0;
			let j = lt + 2;
			for (; j < source.length; j++) {
				const c = source[j];
				if (c === "[") depth++;
				else if (c === "]") depth--;
				else if (c === ">" && depth <= 0) break;
			}
			i = j + 1;
		} else if (source[lt + 1] === "/") {
			const end = source.indexOf(">", lt);
			const name = source.slice(lt + 2, end < 0 ? source.length : end).trim();
			// Close up to the matching open element; ignore an end tag nothing opened.
			const at = stack.map((e) => e.name).lastIndexOf(name);
			if (at > 0) stack.length = at;
			i = end < 0 ? source.length : end + 1;
		} else {
			NAME.lastIndex = lt + 1;
			const name = NAME.exec(source)?.[0];
			if (!name) {
				text("<");
				i = lt + 1;
				continue;
			}
			const element: XmlElement = { name, attrs: {}, children: [] };
			let j = lt + 1 + name.length;
			for (;;) {
				ATTR.lastIndex = j;
				const m = ATTR.exec(source);
				if (!m || m.index !== j) break;
				element.attrs[m[1] as string] = decodeEntities(
					m[2] ?? m[3] ?? m[4] ?? "",
				);
				j = ATTR.lastIndex;
			}
			const end = source.indexOf(">", j);
			const selfClosing = end > 0 && source[end - 1] === "/";
			top().children.push(element);
			if (!selfClosing) stack.push(element);
			i = end < 0 ? source.length : end + 1;
		}
	}
	return root;
}

export const localName = (name: string): string =>
	name.slice(name.indexOf(":") + 1);

export const elements = (node: XmlElement): XmlElement[] =>
	node.children.filter((c): c is XmlElement => typeof c !== "string");

/** Child elements by local name (namespace prefix ignored) or by qualified name when it has a prefix. */
export function children(node: XmlElement, name: string): XmlElement[] {
	const match = name.includes(":")
		? (e: XmlElement) => e.name === name
		: (e: XmlElement) => localName(e.name) === name;
	return elements(node).filter(match);
}

export const child = (
	node: XmlElement | undefined,
	name: string,
): XmlElement | undefined => (node ? children(node, name)[0] : undefined);

/** All text inside, concatenated. */
export function textOf(node: XmlNode | undefined): string {
	if (node === undefined) return "";
	if (typeof node === "string") return node;
	return node.children.map(textOf).join("");
}

const escapeText = (s: string) =>
	s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const escapeAttr = (s: string) => escapeText(s).replace(/"/g, "&quot;");

/** Serialize nodes back to markup (for Atom's inline XHTML content). */
export function serialize(node: XmlNode): string {
	if (typeof node === "string") return escapeText(node);
	const attrs = Object.entries(node.attrs)
		.filter(([k]) => k !== "xmlns" && !k.startsWith("xmlns:"))
		.map(([k, v]) => ` ${localName(k)}="${escapeAttr(v)}"`)
		.join("");
	return `<${localName(node.name)}${attrs}>${node.children.map(serialize).join("")}</${localName(node.name)}>`;
}

export { escapeAttr, escapeText };
