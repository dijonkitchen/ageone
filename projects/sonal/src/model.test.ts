import { describe, expect, test } from "bun:test";
import { findModelsConfig, modelForRole, openRouterChat } from "./model.ts";

const config = {
	roles: { cheap: "openrouter/vendor/small", local: "ollama/x" },
	openRouter: { routing: { zdr: true } },
};

describe("modelForRole", () => {
	test("resolves a role to its OpenRouter model and routing", () => {
		expect(modelForRole("cheap", config)).toEqual({
			model: "vendor/small",
			routing: { zdr: true },
		});
	});
	test("rejects unknown roles and other providers", () => {
		expect(() => modelForRole("nope", config)).toThrow("no model role");
		expect(() => modelForRole("local", config)).toThrow("only openrouter/");
	});
	test("finds the repo's real roles file", () => {
		expect(findModelsConfig()).toMatch(/harness\/models\.json$/);
	});
});

test("openRouterChat sends the role's model with routing and returns the text", async () => {
	let sent: Record<string, unknown> = {};
	const chat = openRouterChat("cheap", config, "KEY", async (_url, init) => {
		sent = JSON.parse(String(init.body));
		return new Response(
			JSON.stringify({ choices: [{ message: { content: "hi" } }] }),
		);
	});
	expect(await chat([{ role: "user", content: "x" }])).toBe("hi");
	expect(sent).toMatchObject({
		model: "vendor/small",
		provider: { zdr: true },
	});
});

test("openRouterChat needs a key", async () => {
	const chat = openRouterChat("cheap", config, undefined);
	await expect(chat([])).rejects.toThrow("OPENROUTER_API_KEY");
});
