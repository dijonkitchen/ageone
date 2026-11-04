// bun run src/cli.ts <video-url>          prints the analysis as JSON
// bun run src/cli.ts --serve [port]       serves the page at http://localhost:<port>
import { join } from "node:path";
import { fileCache } from "./cache.ts";
import { openRouterChat } from "./model.ts";
import { errorPage, formPage, resultPage } from "./page.ts";
import { analyzeUrl } from "./service.ts";
import { youtubeSource } from "./youtube.ts";

// Classification defaults to the cheap role.
const role = process.env.SONAL_ROLE ?? "cheap";
const deps = () => ({
	sources: [youtubeSource()],
	chat: openRouterChat(role),
	cache: fileCache(process.env.SONAL_CACHE ?? join(process.cwd(), ".cache")),
});

const [first, second] = process.argv.slice(2);
if (first === "--serve") {
	const d = deps();
	const server = Bun.serve({
		port: Number(second ?? 3000),
		async fetch(request) {
			const url = new URL(request.url).searchParams.get("url");
			const headers = { "content-type": "text/html; charset=utf-8" };
			if (!url) return new Response(formPage(), { headers });
			try {
				return new Response(resultPage(await analyzeUrl(d, url)), { headers });
			} catch (error) {
				return new Response(errorPage((error as Error).message), {
					status: 502,
					headers,
				});
			}
		},
	});
	console.log(`Sonal at http://localhost:${server.port}`);
} else if (first) {
	console.log(JSON.stringify(await analyzeUrl(deps(), first), null, 2));
} else {
	console.error("usage: cli.ts <video-url> | --serve [port]");
	process.exit(2);
}
