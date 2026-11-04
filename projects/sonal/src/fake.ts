import { wordListSentiment } from "./baseline.ts";
import type { Chat } from "./types.ts";

/** A fake model for tests: labels with the word list, themes by keyword, cites the first comment. */
export const fakeModel = (log: string[] = []): Chat => {
	return async (messages) => {
		const user = messages.find((m) => m.role === "user")?.content ?? "";
		log.push(user);
		const data = JSON.parse(user) as {
			comments: { id: string; text: string }[];
			themes?: string[];
		};
		if (data.themes) {
			const first = data.comments[0];
			return JSON.stringify({
				summary: [
					{ text: "Viewers mostly reacted to the audio.", cites: [first?.id] },
				],
			});
		}
		return JSON.stringify({
			results: data.comments.map((c) => ({
				id: c.id,
				sentiment: wordListSentiment(c.text),
				themes: /audio|mic|sound/i.test(c.text) ? ["audio"] : [],
			})),
		});
	};
};
