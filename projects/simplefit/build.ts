// Build the PWA into dist/ (or the folder given): bundle src/app.ts, copy public/, draw the PNG icons, and stamp
// the service worker with a hash of every file, so each build is one cache that replaces the last.
import { createHash } from "node:crypto";
import {
	cpSync,
	readdirSync,
	readFileSync,
	rmSync,
	writeFileSync,
} from "node:fs";
import { join } from "node:path";
import { encodePng, icon } from "./src/png";

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
for (const size of [180, 512])
	writeFileSync(
		join(out, `icon-${size}.png`),
		encodePng(size, size, icon(size)),
	);
const hash = createHash("sha256");
for (const file of readdirSync(out).sort())
	if (file !== "sw.js") hash.update(file).update(readFileSync(join(out, file)));
const sw = join(out, "sw.js");
writeFileSync(
	sw,
	readFileSync(sw, "utf8").replace(
		"__VERSION__",
		hash.digest("hex").slice(0, 12),
	),
);
console.log(`built ${out}`);
