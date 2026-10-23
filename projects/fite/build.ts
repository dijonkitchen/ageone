// Build the game into dist/ (or the folder given): bundle src/app.ts and copy public/.
import { cpSync, rmSync } from "node:fs";
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
console.log(`built ${out}`);
