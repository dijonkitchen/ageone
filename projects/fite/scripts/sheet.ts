// Regenerate sprites/sheet.png from the sprite code: `bun run sheet`. CI fails if the committed sheet differs.
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { encodePng } from "../src/png";
import { sheet } from "../src/sprites";

const out = join(import.meta.dir, "..", "sprites", "sheet.png");
writeFileSync(out, encodePng(sheet()));
console.log(`wrote ${out}`);
