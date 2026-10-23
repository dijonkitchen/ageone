import type { Analysis, Sentiment } from "./types.ts";

export const escapeHtml = (text: string): string =>
	text
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
		.replace(/'/g, "&#39;");

const shell = (title: string, body: string) => `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)}</title>
<style>
:root { color-scheme: light dark; --pos: #2a8a4a; --neu: #8a8a8a; --neg: #c0392b; }
body { font: 16px/1.5 system-ui, sans-serif; max-width: 46rem; margin: 0 auto; padding: 1rem; }
form { display: flex; gap: .5rem; } input[type=url] { flex: 1; padding: .5rem; }
.bar { display: flex; height: 1.25rem; border-radius: 4px; overflow: hidden; }
.bar span { display: block; } .legend { display: flex; gap: 1rem; flex-wrap: wrap; }
blockquote { margin: .25rem 0; padding-left: .75rem; border-left: 3px solid #8885; }
a.cite { font-size: .8em; vertical-align: super; }
.error { color: var(--neg); }
</style>
</head>
<body>
<h1>Sonal</h1>
<form method="get" action="/"><input type="url" name="url" placeholder="https://www.youtube.com/watch?v=..." required aria-label="YouTube video URL"><button>Analyze</button></form>
${body}
</body>
</html>`;

export const formPage = (): string => shell("Sonal", "");

export const errorPage = (message: string): string =>
	shell("Sonal", `<p class="error" role="alert">${escapeHtml(message)}</p>`);

const COLORS: Record<Sentiment, string> = {
	positive: "var(--pos)",
	neutral: "var(--neu)",
	negative: "var(--neg)",
};

export const resultPage = (a: Analysis): string => {
	const byId = new Map(a.comments.map((c) => [c.id, c]));
	const total = a.classified.length;
	const pct = (n: number) => (total ? Math.round((100 * n) / total) : 0);
	const sentiments = ["positive", "neutral", "negative"] as const;
	const bar = sentiments
		.map(
			(s) =>
				`<span style="width:${total ? (100 * a.split[s]) / total : 0}%;background:${COLORS[s]}" title="${s}"></span>`,
		)
		.join("");
	const legend = sentiments
		.map((s) => `<span>${s}: ${a.split[s]} (${pct(a.split[s])}%)</span>`)
		.join("");
	const quote = (id: string) => {
		const c = byId.get(id);
		return c
			? `<blockquote id="c-${escapeHtml(id)}">${escapeHtml(c.text.slice(0, 300))} <small>— ${escapeHtml(c.author)}, ${c.likes} likes</small></blockquote>`
			: "";
	};
	const themes = a.themes
		.map(
			(t) =>
				`<section><h3>${escapeHtml(t.name)} <small>(${t.count})</small></h3>${t.examples.map(quote).join("")}</section>`,
		)
		.join("");
	const summary = a.summary
		.map(
			(s) =>
				`<p>${escapeHtml(s.text)}${s.cites
					.map(
						(id, i) =>
							`<a class="cite" href="#c-${escapeHtml(id)}">[${i + 1}]</a>`,
					)
					.join("")}</p>`,
		)
		.join("");
	const cited = [...new Set(a.summary.flatMap((s) => s.cites))]
		.map(quote)
		.join("");
	return shell(
		`Sonal: ${a.video.title}`,
		`<h2>${escapeHtml(a.video.title)}</h2>
<p>${total} of ${a.comments.length} comments classified.</p>
<h2>Sentiment</h2><div class="bar" role="img" aria-label="sentiment split">${bar}</div><p class="legend">${legend}</p>
<h2>Summary</h2>${summary || "<p>No summary.</p>"}
<h2>Themes</h2>${themes || "<p>No themes.</p>"}
<h2>Cited comments</h2>${cited}`,
	);
};
