// Feed HTML to safe HTML: DOMPurify (audited) with a strict policy on top. Scripts, event handlers, styles,
// forms, frames, and media go; links keep only http, https, and mailto and open in a new tab without a referrer;
// images don't load unless asked, since loading them would contact a third party.

import createDOMPurify, { type Config } from "dompurify";

export interface SanitizeOptions {
	base?: string | null; // resolves relative links and images
	images?: boolean; // load images; off keeps the reader's only requests to the feeds themselves
}

const CONFIG: Config = {
	USE_PROFILES: { html: true },
	FORBID_TAGS: [
		"style",
		"form",
		"input",
		"button",
		"textarea",
		"select",
		"option",
		"iframe",
		"frame",
		"frameset",
		"object",
		"embed",
		"video",
		"audio",
		"source",
		"track",
		"picture",
		"link",
		"meta",
		"base",
		"svg",
		"math",
	],
	FORBID_ATTR: [
		"style",
		"srcset",
		"background",
		"ping",
		"formaction",
		"action",
		"poster",
		"id",
		"name",
	],
	ALLOW_DATA_ATTR: false,
	ALLOWED_URI_REGEXP: /^(?:https?:|mailto:|[^a-z]|[a-z+.-]+(?:[^a-z+.\-:]|$))/i,
};

const SAFE_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);
const PLACEHOLDER = "fread-image";

function safeUrl(
	value: string | null,
	base: string | null | undefined,
): string | null {
	if (!value) return null;
	try {
		const url = new URL(value.trim(), base ?? undefined);
		return SAFE_PROTOCOLS.has(url.protocol) ? url.href : null;
	} catch {
		return null;
	}
}

export function sanitize(
	html: string,
	// biome-ignore lint/suspicious/noExplicitAny: DOMPurify takes any window-like object (the page's, or jsdom's in tests).
	window: any,
	options: SanitizeOptions = {},
): string {
	const purify = createDOMPurify(window);
	purify.addHook("afterSanitizeAttributes", (node: Element) => {
		const tag = node.tagName.toLowerCase();
		if (node.hasAttribute("href")) {
			const href = safeUrl(node.getAttribute("href"), options.base);
			if (href) node.setAttribute("href", href);
			else node.removeAttribute("href");
		}
		if (tag === "a") {
			node.setAttribute("target", "_blank");
			node.setAttribute("rel", "noopener noreferrer nofollow");
			node.setAttribute("referrerpolicy", "no-referrer");
		}
		if (tag === "img") {
			const src = safeUrl(node.getAttribute("src"), options.base);
			node.removeAttribute("src");
			if (src?.startsWith("http")) {
				node.setAttribute("referrerpolicy", "no-referrer");
				node.setAttribute("loading", "lazy");
				if (options.images) node.setAttribute("src", src);
				else {
					// Kept as a title so the page can load it on request; never as a live URL.
					node.setAttribute(
						"title",
						`${node.getAttribute("title") ?? ""}`.trim(),
					);
					node.setAttribute("alt", node.getAttribute("alt") || "image");
					node.setAttribute("class", PLACEHOLDER);
					node.setAttribute("data-fread-src", src);
				}
			}
		} else if (node.hasAttribute("src")) {
			node.removeAttribute("src");
		}
	});
	purify.addHook("uponSanitizeAttribute", (_node, data) => {
		// Our own placeholder attribute only; feeds can't set data-* (ALLOW_DATA_ATTR is off).
		if (data.attrName === "data-fread-src") data.keepAttr = false;
	});
	const out = purify.sanitize(html, CONFIG) as unknown as string;
	purify.removeAllHooks();
	return out;
}

export const IMAGE_PLACEHOLDER_CLASS = PLACEHOLDER;
