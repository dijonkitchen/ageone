import { askStructured } from "./quarantine.ts";
import {
	type Chat,
	type Classified,
	type Comment,
	SENTIMENTS,
	type Sentiment,
} from "./types.ts";

const SYSTEM =
	"You label YouTube comments. For each comment give its sentiment toward the video " +
	`(${SENTIMENTS.join(", ")}) and up to 3 short lowercase themes (1-3 words each, ` +
	'for example "editing" or "sound quality"). Reuse the same theme wording across comments. ' +
	'Reply as {"results":[{"id":"<comment id>","sentiment":"...","themes":["..."]}]} with one entry per comment.';

const MAX_COMMENT_CHARS = 600;

export const BATCH_SIZE = 25;

const THEME = /^[a-z0-9][a-z0-9 '&-]{0,31}$/;

/** Accepts only known IDs and sentiments; themes are normalized, and any bad entry is dropped. */
export const validateBatch =
	(ids: ReadonlySet<string>) =>
	(value: unknown): Classified[] => {
		const results = (value as { results?: unknown })?.results;
		if (!Array.isArray(results)) throw new Error("results is not an array");
		const seen = new Set<string>();
		const out: Classified[] = [];
		for (const r of results as Record<string, unknown>[]) {
			const id = r?.id;
			if (typeof id !== "string" || !ids.has(id) || seen.has(id)) continue;
			if (!SENTIMENTS.includes(r.sentiment as Sentiment)) continue;
			const themes = Array.isArray(r.themes)
				? [
						...new Set(
							r.themes
								.filter((t): t is string => typeof t === "string")
								.map((t) => t.toLowerCase().trim())
								.filter((t) => THEME.test(t)),
						),
					].slice(0, 3)
				: [];
			seen.add(id);
			out.push({ id, sentiment: r.sentiment as Sentiment, themes });
		}
		if (out.length === 0) throw new Error("no valid results");
		return out;
	};

/** Batched labels from the model; comments the model skipped or garbled stay unclassified. */
export const classify = async (
	chat: Chat,
	comments: readonly Comment[],
	batchSize = BATCH_SIZE,
): Promise<Classified[]> => {
	const out: Classified[] = [];
	for (let i = 0; i < comments.length; i += batchSize) {
		const batch = comments.slice(i, i + batchSize);
		const payload = JSON.stringify({
			comments: batch.map((c) => ({
				id: c.id,
				text: c.text.slice(0, MAX_COMMENT_CHARS),
			})),
		});
		out.push(
			...(await askStructured(
				chat,
				SYSTEM,
				payload,
				validateBatch(new Set(batch.map((c) => c.id))),
			)),
		);
	}
	return out;
};
