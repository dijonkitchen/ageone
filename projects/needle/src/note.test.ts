import { expect, test } from "bun:test";
import { type Note, noteId, parseNote, serializeNote, slugify } from "./note";

const note: Note = {
	id: noteId("What is “Rust”?", "2026-10-23T12:00:00.000Z"),
	question: "What is “Rust”?",
	created: "2026-10-23T12:00:00.000Z",
	model: "default (anthropic/claude-sonnet-5)",
	answer: "A language.[^1]",
	sources: [
		{
			title: "Rust [site]",
			url: "https://rust-lang.org",
			snippet: "Fast — safe",
		},
	],
};

test("a note round-trips through Markdown", () => {
	const md = serializeNote(note);
	expect(md).toContain("schema: research/v1");
	expect(md).toContain(
		"[^1]: [Rust site](https://rust-lang.org) — Fast — safe",
	);
	const parsed = parseNote(md);
	expect(parsed).toEqual({
		...note,
		sources: [
			{
				title: "Rust site",
				url: "https://rust-lang.org",
				snippet: "Fast — safe",
			},
		],
	});
});

test("ids are sortable, safe file names", () => {
	expect(note.id).toBe("2026-10-23T12-00-00-000Z-what-is-rust");
	expect(slugify("???")).toBe("note");
});

test("text without research/v1 frontmatter is rejected", () => {
	expect(() => parseNote("# hi")).toThrow();
	expect(() => parseNote("---\nschema: other/v1\n---\nx")).toThrow();
});
