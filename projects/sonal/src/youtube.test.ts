import { describe, expect, test } from "bun:test";
import page1 from "./fixtures/youtube-comments.json";
import page2 from "./fixtures/youtube-comments-2.json";
import video from "./fixtures/youtube-video.json";
import { parseVideoId, youtubeSource } from "./youtube.ts";

describe("parseVideoId", () => {
	test.each([
		["https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=5s", "dQw4w9WgXcQ"],
		["https://youtu.be/dQw4w9WgXcQ?si=x", "dQw4w9WgXcQ"],
		["https://m.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"],
		["https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"],
		["dQw4w9WgXcQ", "dQw4w9WgXcQ"],
	])("%s", (input, id) => expect(parseVideoId(input)).toBe(id));

	test.each([
		"https://example.com/watch?v=dQw4w9WgXcQ",
		"https://www.youtube.com/watch?v=short",
		"https://www.youtube.com/",
		"not a url",
	])("rejects %s", (input) => expect(parseVideoId(input)).toBeNull());
});

const recorded = () => {
	const calls: string[] = [];
	const fetcher = async (url: string) => {
		calls.push(url);
		const u = new URL(url);
		const body = u.pathname.endsWith("/videos")
			? video
			: u.searchParams.get("pageToken")
				? page2
				: page1;
		return new Response(JSON.stringify(body));
	};
	return { calls, source: youtubeSource("KEY", fetcher) };
};

describe("youtubeSource", () => {
	test("fetches the title", async () => {
		expect((await recorded().source.fetchVideo("dQw4w9WgXcQ")).title).toBe(
			"How tides work",
		);
	});

	test("pages through top-level comments", async () => {
		const { source, calls } = recorded();
		const comments = await source.fetchComments("dQw4w9WgXcQ", 10);
		expect(comments.map((c) => c.id)).toEqual(["Ug1", "Ug2", "Ug3"]);
		expect(comments[0]).toMatchObject({ author: "Ana", likes: 12 });
		expect(comments[2]?.text).toBe("What mic is that?");
		expect(calls).toHaveLength(2);
	});

	test("stops at the limit", async () => {
		expect(
			await recorded().source.fetchComments("dQw4w9WgXcQ", 1),
		).toHaveLength(1);
	});

	test("needs a key and never leaks it in errors", async () => {
		await expect(
			youtubeSource(undefined).fetchVideo("dQw4w9WgXcQ"),
		).rejects.toThrow("YOUTUBE_API_KEY");
		const failing = youtubeSource(
			"SECRET",
			async () => new Response("quota", { status: 403 }),
		);
		await expect(failing.fetchVideo("dQw4w9WgXcQ")).rejects.toThrow(
			/403: quota$/,
		);
	});
});
