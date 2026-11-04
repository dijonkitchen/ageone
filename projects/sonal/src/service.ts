import { analyze } from "./analyze.ts";
import type { fileCache } from "./cache.ts";
import type { Analysis, Chat, CommentSource } from "./types.ts";

export const COMMENT_LIMIT = 200;

export interface Deps {
	readonly sources: readonly CommentSource[];
	readonly chat: Chat;
	readonly cache: ReturnType<typeof fileCache>;
}

/** The analysis for a pasted URL: cached per video, else fetched and classified once. */
export const analyzeUrl = async (
	deps: Deps,
	url: string,
	limit = COMMENT_LIMIT,
): Promise<Analysis> => {
	for (const source of deps.sources) {
		const id = source.parse(url);
		if (!id) continue;
		const cached = deps.cache.get(source.platform, id);
		if (cached) return cached;
		const [video, comments] = await Promise.all([
			source.fetchVideo(id),
			source.fetchComments(id, limit),
		]);
		const analysis = await analyze(deps.chat, video, comments);
		deps.cache.set(analysis);
		return analysis;
	}
	throw new Error("not a supported video URL");
};
