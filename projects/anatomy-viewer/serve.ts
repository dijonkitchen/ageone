// Serve dist/ locally (run `bun run build` first; `bun run serve` does both). PORT picks the port.
import { join, normalize } from "node:path";

const root = join(import.meta.dir, "dist");
const server = Bun.serve({
	port: Number(process.env.PORT ?? 8080),
	async fetch(req) {
		const path = normalize(
			decodeURIComponent(new URL(req.url).pathname),
		).replace(/^(\.\.[/\\])+/, "");
		const file = Bun.file(
			join(root, path.endsWith("/") ? `${path}index.html` : path),
		);
		return (await file.exists())
			? new Response(file)
			: new Response("not found", { status: 404 });
	},
});
console.log(`viewing at http://localhost:${server.port}/`);
