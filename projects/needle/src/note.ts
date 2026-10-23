// The research/v1 note: frontmatter that Obsidian shows as properties, a cited answer with footnotes.
export type Source = { title: string; url: string; snippet: string };

export type Note = {
	id: string;
	question: string;
	created: string;
	model: string;
	answer: string;
	sources: Source[];
};

export const SCHEMA = "research/v1";

export function slugify(text: string): string {
	const slug = text
		.toLowerCase()
		.replace(/[^\p{L}\p{N}]+/gu, "-")
		.replace(/^-+|-+$/g, "")
		.slice(0, 48)
		.replace(/-+$/, "");
	return slug || "note";
}

export function noteId(question: string, created: string): string {
	return `${created.replace(/[:.]/g, "-")}-${slugify(question)}`;
}

export function notePath(id: string): string {
	return `research/${id}.md`;
}

// Single-line text keeps frontmatter values valid YAML double-quoted strings and Markdown links intact.
const oneLine = (text: string) => text.replace(/\s+/g, " ").trim();

export function serializeNote(note: Note): string {
	const frontmatter = [
		"---",
		`schema: ${SCHEMA}`,
		`id: ${JSON.stringify(note.id)}`,
		`question: ${JSON.stringify(oneLine(note.question))}`,
		`created: ${JSON.stringify(note.created)}`,
		`model: ${JSON.stringify(note.model)}`,
		`sources: ${note.sources.length}`,
		"---",
	];
	const footnotes = note.sources.map(
		(s, i) =>
			`[^${i + 1}]: [${oneLine(s.title).replace(/[[\]]/g, "")}](${s.url}) — ${oneLine(s.snippet)}`,
	);
	return [
		...frontmatter,
		"",
		`# ${oneLine(note.question)}`,
		"",
		note.answer.trim(),
		...(footnotes.length ? ["", ...footnotes] : []),
		"",
	].join("\n");
}

function parseValue(raw: string): unknown {
	try {
		return JSON.parse(raw);
	} catch {
		return raw; // an unquoted YAML scalar, such as the schema
	}
}

export function parseNote(markdown: string): Note {
	const match = /^---\n([\s\S]*?)\n---\n/.exec(markdown);
	if (!match) throw new Error("note has no frontmatter");
	const fields = new Map<string, unknown>();
	for (const line of (match[1] ?? "").split("\n")) {
		const m = /^(\w+): (.*)$/.exec(line);
		if (m) fields.set(m[1] ?? "", parseValue(m[2] ?? ""));
	}
	if (fields.get("schema") !== SCHEMA)
		throw new Error("not a research/v1 note");
	const body = markdown.slice(match[0].length);
	const sources: Source[] = [];
	const lines = body.split("\n");
	const answerLines: string[] = [];
	for (const line of lines) {
		const f = /^\[\^\d+\]: \[(.*)\]\((\S+)\) — (.*)$/.exec(line);
		if (f)
			sources.push({ title: f[1] ?? "", url: f[2] ?? "", snippet: f[3] ?? "" });
		else answerLines.push(line);
	}
	const answer = answerLines
		.join("\n")
		.replace(/^\s*# .*\n/, "")
		.trim();
	const str = (key: string) => String(fields.get(key) ?? "");
	return {
		id: str("id"),
		question: str("question"),
		created: str("created"),
		model: str("model"),
		answer,
		sources,
	};
}
