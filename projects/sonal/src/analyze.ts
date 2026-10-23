import { classify } from "./classify.ts";
import { askStructured, plainText } from "./quarantine.ts";
import type {
	Analysis,
	Chat,
	Classified,
	Comment,
	Sentiment,
	Theme,
	Video,
} from "./types.ts";

export const MAX_THEMES = 6;
export const EXAMPLES_PER_THEME = 3;

export const sentimentSplit = (
	classified: readonly Classified[],
): Record<Sentiment, number> => {
	const split = { positive: 0, neutral: 0, negative: 0 };
	for (const c of classified) split[c.sentiment]++;
	return split;
};

/** The most common themes, each with its most liked example comments. */
export const topThemes = (
	comments: readonly Comment[],
	classified: readonly Classified[],
): Theme[] => {
	const likes = new Map(comments.map((c) => [c.id, c.likes]));
	const byTheme = new Map<string, string[]>();
	for (const c of classified) {
		for (const theme of c.themes) {
			byTheme.set(theme, [...(byTheme.get(theme) ?? []), c.id]);
		}
	}
	return [...byTheme.entries()]
		.map(([name, ids]) => ({
			name,
			count: ids.length,
			examples: [...ids]
				.sort((a, b) => (likes.get(b) ?? 0) - (likes.get(a) ?? 0))
				.slice(0, EXAMPLES_PER_THEME),
		}))
		.sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
		.slice(0, MAX_THEMES);
};

const SUMMARY_SYSTEM =
	"Summarize how viewers reacted to a video in 3 to 5 plain sentences. Each sentence must cite " +
	"the ids of the comments that support it. Use only the comments given. " +
	'Reply as {"summary":[{"text":"...","cites":["<comment id>"]}]}.';

/** Sentences whose citations all exist; uncited or unknown-cite sentences are dropped. */
export const validateSummary =
	(ids: ReadonlySet<string>) =>
	(value: unknown): Analysis["summary"] => {
		const items = (value as { summary?: unknown })?.summary;
		if (!Array.isArray(items)) throw new Error("summary is not an array");
		const out: { text: string; cites: string[] }[] = [];
		for (const item of items as Record<string, unknown>[]) {
			if (typeof item?.text !== "string" || !Array.isArray(item.cites))
				continue;
			const cites = [
				...new Set(
					item.cites.filter((c): c is string => typeof c === "string"),
				),
			];
			const text = plainText(item.text);
			if (text && cites.length > 0 && cites.every((c) => ids.has(c))) {
				out.push({ text, cites });
			}
		}
		if (out.length === 0) throw new Error("no cited sentences");
		return out;
	};

const SUMMARY_COMMENTS = 40;

export const summarize = async (
	chat: Chat,
	video: Video,
	comments: readonly Comment[],
	themes: readonly Theme[],
): Promise<Analysis["summary"]> => {
	const byId = new Map(comments.map((c) => [c.id, c]));
	const picked = new Map<string, Comment>();
	for (const theme of themes) {
		for (const id of theme.examples) {
			const c = byId.get(id);
			if (c) picked.set(id, c);
		}
	}
	for (const c of [...comments].sort((a, b) => b.likes - a.likes)) {
		if (picked.size >= SUMMARY_COMMENTS) break;
		picked.set(c.id, c);
	}
	const payload = JSON.stringify({
		video: video.title,
		themes: themes.map((t) => t.name),
		comments: [...picked.values()].map((c) => ({
			id: c.id,
			text: c.text.slice(0, 400),
		})),
	});
	return askStructured(
		chat,
		SUMMARY_SYSTEM,
		payload,
		validateSummary(new Set(picked.keys())),
	);
};

export const analyze = async (
	chat: Chat,
	video: Video,
	comments: readonly Comment[],
): Promise<Analysis> => {
	const classified = await classify(chat, comments);
	const themes = topThemes(comments, classified);
	const summary =
		comments.length > 0 ? await summarize(chat, video, comments, themes) : [];
	return {
		video,
		comments,
		classified,
		split: sentimentSplit(classified),
		themes,
		summary,
	};
};
