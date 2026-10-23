// Static server for dist/ and a Chromium launcher, so end-to-end tests run against the built PWA.
import { existsSync, mkdtempSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { type Browser, chromium } from "playwright-core";

const dist = join(import.meta.dir, "..", "dist");

export function serve() {
	return Bun.serve({
		port: 0,
		async fetch(req) {
			const path = new URL(req.url).pathname;
			const file = Bun.file(join(dist, path === "/" ? "index.html" : path));
			return (await file.exists())
				? new Response(file)
				: new Response("not found", { status: 404 });
		},
	});
}

// PLAYWRIGHT_BROWSERS_PATH holds the browsers `playwright install` or the cloud image provides.
function chromiumPath(): string | undefined {
	const root =
		process.env.PLAYWRIGHT_BROWSERS_PATH ??
		join(process.env.HOME ?? "", ".cache/ms-playwright");
	if (!existsSync(root)) return undefined;
	for (const dir of readdirSync(root)
		.filter((d) => d.startsWith("chromium-"))
		.sort()
		.reverse())
		for (const sub of ["chrome-linux/chrome", "chrome-linux64/chrome"]) {
			const exe = join(root, dir, sub);
			if (existsSync(exe)) return exe;
		}
	return undefined;
}

// Bun cannot drive Playwright's pipe transport, so Chromium is started by hand and reached over CDP.
export async function launch(): Promise<Browser & { stopChromium(): void }> {
	const exe = chromiumPath();
	if (!exe)
		throw new Error(
			"no Chromium found: run `bunx playwright-core install chromium`",
		);
	const dir = mkdtempSync(join(tmpdir(), "needle-chromium-"));
	const proc = Bun.spawn(
		[
			exe,
			"--headless",
			"--no-sandbox",
			"--disable-gpu",
			"--remote-debugging-port=0",
			`--user-data-dir=${dir}`,
			"about:blank",
		],
		{ stdout: "ignore", stderr: "pipe" },
	);
	const decoder = new TextDecoder();
	let log = "";
	let endpoint: string | undefined;
	for await (const chunk of proc.stderr) {
		log += decoder.decode(chunk);
		endpoint = /DevTools listening on (ws:\/\/\S+)/.exec(log)?.[1];
		if (endpoint) break;
	}
	if (!endpoint) throw new Error(`Chromium did not start:\n${log}`);
	const browser = await chromium.connectOverCDP(endpoint);
	return Object.assign(browser, {
		stopChromium() {
			proc.kill();
			rmSync(dir, { recursive: true, force: true });
		},
	});
}
