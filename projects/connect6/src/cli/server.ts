/**
 * Local web server: serves the UI (bundled by Bun from index.html) and
 * forwards the browser LLM player's turns to OpenRouter, so the API key and
 * the model choice stay on this machine's server, never in the page.
 *
 *   bun run dev            # http://localhost:3000
 */

import index from "../../index.html";
import type { ChatMessage } from "../core/index.js";
import { modelForRole, openRouterChat } from "./openrouter.js";

export const chatHandler = async (request: Request): Promise<Response> => {
	try {
		const body = (await request.json()) as {
			role?: string;
			messages?: ChatMessage[];
		};
		const chat = openRouterChat(modelForRole(body.role ?? "cheap"));
		return Response.json(await chat(body.messages ?? []));
	} catch (error) {
		return Response.json({ error: (error as Error).message }, { status: 503 });
	}
};

if (import.meta.main) {
	const server = Bun.serve({
		port: Number(process.env.PORT ?? 3000),
		development: process.env.NODE_ENV !== "production",
		routes: {
			"/": index,
			"/api/chat": { POST: chatHandler },
		},
	});
	console.log(`Connect6 at ${server.url}`);
}
