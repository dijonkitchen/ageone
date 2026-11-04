import type { Comment, CommentSource, Video } from "./types.ts";

type Fetch = (url: string) => Promise<Response>;

const ID = /^[A-Za-z0-9_-]{11}$/;

/** The 11-character video ID from a watch, short, embed, shorts, or live URL, or a bare ID. */
export const parseVideoId = (input: string): string | null => {
	const text = input.trim();
	if (ID.test(text)) return text;
	let url: URL;
	try {
		url = new URL(text);
	} catch {
		return null;
	}
	const host = url.hostname.replace(/^(www|m|music)\./, "");
	let candidate: string | null = null;
	if (host === "youtu.be") {
		candidate = url.pathname.split("/")[1] ?? null;
	} else if (host === "youtube.com" || host === "youtube-nocookie.com") {
		const [, first, second] = url.pathname.split("/");
		if (first === "watch") candidate = url.searchParams.get("v");
		else if (["embed", "shorts", "live", "v"].includes(first ?? "")) {
			candidate = second ?? null;
		}
	}
	return candidate && ID.test(candidate) ? candidate : null;
};

interface ThreadsPage {
	nextPageToken?: string;
	items?: {
		id: string;
		snippet: {
			topLevelComment: {
				snippet: {
					authorDisplayName: string;
					textOriginal?: string;
					textDisplay: string;
					likeCount?: number;
				};
			};
		};
	}[];
}

const API = "https://www.googleapis.com/youtube/v3";

/** Top-level comments through the YouTube Data API; the key comes from the caller (the environment). */
export const youtubeSource = (
	apiKey: string | undefined = process.env.YOUTUBE_API_KEY,
	fetcher: Fetch = (url) => fetch(url),
): CommentSource => {
	const get = async <T>(path: string, params: Record<string, string>) => {
		if (!apiKey) throw new Error("YOUTUBE_API_KEY is not set");
		const query = new URLSearchParams({ ...params, key: apiKey });
		const response = await fetcher(`${API}/${path}?${query}`);
		if (!response.ok) {
			// The URL carries the key, so only the body is reported.
			throw new Error(`YouTube ${response.status}: ${await response.text()}`);
		}
		return (await response.json()) as T;
	};
	return {
		platform: "youtube",
		parse: parseVideoId,
		async fetchVideo(id): Promise<Video> {
			const data = await get<{ items?: { snippet: { title: string } }[] }>(
				"videos",
				{ part: "snippet", id },
			);
			const item = data.items?.[0];
			if (!item) throw new Error(`no YouTube video ${id}`);
			return { platform: "youtube", id, title: item.snippet.title };
		},
		async fetchComments(id, limit): Promise<Comment[]> {
			const comments: Comment[] = [];
			let pageToken: string | undefined;
			while (comments.length < limit) {
				const page = await get<ThreadsPage>("commentThreads", {
					part: "snippet",
					videoId: id,
					maxResults: String(Math.min(100, limit - comments.length)),
					order: "relevance",
					textFormat: "plainText",
					...(pageToken ? { pageToken } : {}),
				});
				for (const item of page.items ?? []) {
					const s = item.snippet.topLevelComment.snippet;
					comments.push({
						id: item.id,
						author: s.authorDisplayName,
						text: (s.textOriginal ?? s.textDisplay).trim(),
						likes: s.likeCount ?? 0,
					});
				}
				pageToken = page.nextPageToken;
				if (!pageToken) break;
			}
			return comments.slice(0, limit);
		},
	};
};
