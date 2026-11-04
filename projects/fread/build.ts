// Build the PWA into dist/: bundle src/app.ts, copy public/, and stamp the service worker's cache version.
import { createHash } from "node:crypto";
import { cpSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const out = process.argv[2] ?? join(import.meta.dir, "dist");
rmSync(out, { recursive: true, force: true });
const result = await Bun.build({
	entrypoints: [join(import.meta.dir, "src/app.ts")],
	outdir: out,
	minify: true,
	target: "browser",
});
if (!result.success) {
	for (const log of result.logs) console.error(log);
	process.exit(1);
}
cpSync(join(import.meta.dir, "public"), out, { recursive: true });
const hash = createHash("sha256");
for (const file of [
	"app.js",
	"index.html",
	"styles.css",
	"manifest.webmanifest",
	"icon.svg",
])
	hash.update(readFileSync(join(out, file)));
const sw = join(out, "sw.js");
writeFileSync(
	sw,
	readFileSync(sw, "utf8").replace(
		"__VERSION__",
		hash.digest("hex").slice(0, 12),
	),
);
console.log(`built ${out}`);
