export interface Comment {
	/** Stable ID from the platform; cited by the summary. */
	readonly id: string;
	readonly author: string;
	readonly text: string;
	readonly likes: number;
}

export interface Video {
	readonly platform: string;
	readonly id: string;
	readonly title: string;
}

/** A platform's comments for one link. Other platforms add a source, nothing else changes. */
export interface CommentSource {
	readonly platform: string;
	/** The platform's ID for a URL, or null when the URL isn't this platform's. */
	parse(url: string): string | null;
	fetchVideo(id: string): Promise<Video>;
	fetchComments(id: string, limit: number): Promise<Comment[]>;
}

export const SENTIMENTS = ["positive", "neutral", "negative"] as const;
export type Sentiment = (typeof SENTIMENTS)[number];

export interface Classified {
	readonly id: string;
	readonly sentiment: Sentiment;
	/** Short lowercase theme labels, at most three. */
	readonly themes: readonly string[];
}

export interface Theme {
	readonly name: string;
	readonly count: number;
	/** Comment IDs, most liked first. */
	readonly examples: readonly string[];
}

export interface Analysis {
	readonly video: Video;
	readonly comments: readonly Comment[];
	readonly classified: readonly Classified[];
	readonly split: Record<Sentiment, number>;
	readonly themes: readonly Theme[];
	/** Summary sentences, each citing comment IDs that exist in `comments`. */
	readonly summary: readonly { text: string; cites: readonly string[] }[];
}

/** One model call; the role decides which model, never a model ID in code. */
export type Chat = (
	messages: readonly { role: "system" | "user"; content: string }[],
) => Promise<string>;
