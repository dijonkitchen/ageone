// Build the static page into dist/ (or the folder given): bundle src/ui/app.ts and copy public/.
import { cpSync, rmSync } from "node:fs";
import { join } from "node:path";

const out = process.argv[2] ?? join(import.meta.dir, "dist");
rmSync(out, { recursive: true, force: true });
const result = await Bun.build({
	entrypoints: [join(import.meta.dir, "src/ui/app.ts")],
	outdir: out,
	minify: true,
	splitting: true,
	target: "browser",
	// QuickJS's single-file build only imports Node's "module" when it runs under Node; leave it out.
	external: ["module"],
});
if (!result.success) {
	for (const log of result.logs) console.error(log);
	process.exit(1);
}
cpSync(join(import.meta.dir, "public"), out, { recursive: true });
console.log(`built ${out}`);
