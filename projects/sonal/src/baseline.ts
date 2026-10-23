// The old repo's approach, kept as the bar the LLM classifier must beat: count positive and
// negative words from a fixed list.
import type { Sentiment } from "./types.ts";

const POSITIVE = new Set([
	"good",
	"great",
	"love",
	"loved",
	"amazing",
	"awesome",
	"best",
	"excellent",
	"nice",
	"beautiful",
	"perfect",
	"wonderful",
	"fantastic",
	"thanks",
	"helpful",
	"brilliant",
	"enjoy",
	"enjoyed",
	"favorite",
	"happy",
]);
const NEGATIVE = new Set([
	"bad",
	"worst",
	"hate",
	"hated",
	"terrible",
	"awful",
	"boring",
	"stupid",
	"waste",
	"annoying",
	"poor",
	"horrible",
	"disappointing",
	"disappointed",
	"useless",
	"wrong",
	"sucks",
	"ugly",
	"cringe",
	"garbage",
]);

export const wordListSentiment = (text: string): Sentiment => {
	let score = 0;
	for (const word of text.toLowerCase().match(/[a-z']+/g) ?? []) {
		if (POSITIVE.has(word)) score++;
		else if (NEGATIVE.has(word)) score--;
	}
	return score > 0 ? "positive" : score < 0 ? "negative" : "neutral";
};
