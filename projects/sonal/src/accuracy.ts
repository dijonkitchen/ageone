import { wordListSentiment } from "./baseline.ts";
import { classify } from "./classify.ts";
import type { Chat, Comment, Sentiment } from "./types.ts";

export interface Labeled {
	readonly id: string;
	readonly text: string;
	readonly label: Sentiment;
}

const asComments = (set: readonly Labeled[]): Comment[] =>
	set.map((l) => ({ id: l.id, author: "", text: l.text, likes: 0 }));

export const baselineAccuracy = (set: readonly Labeled[]): number =>
	set.filter((l) => wordListSentiment(l.text) === l.label).length / set.length;

/** Share of the labeled set the model classifier gets right; unclassified comments count as wrong. */
export const modelAccuracy = async (
	chat: Chat,
	set: readonly Labeled[],
): Promise<number> => {
	const got = new Map(
		(await classify(chat, asComments(set))).map((c) => [c.id, c.sentiment]),
	);
	return set.filter((l) => got.get(l.id) === l.label).length / set.length;
};
