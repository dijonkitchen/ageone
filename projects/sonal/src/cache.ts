import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Analysis } from "./types.ts";

/** One JSON file per video, so a repeat visit neither refetches nor reclassifies. */
export const fileCache = (dir: string) => {
	const path = (platform: string, id: string) =>
		join(dir, `${platform}-${id.replace(/[^A-Za-z0-9_-]/g, "_")}.json`);
	return {
		get(platform: string, id: string): Analysis | null {
			const file = path(platform, id);
			if (!existsSync(file)) return null;
			try {
				return JSON.parse(readFileSync(file, "utf8")) as Analysis;
			} catch {
				return null;
			}
		},
		set(analysis: Analysis): void {
			mkdirSync(dir, { recursive: true });
			writeFileSync(
				path(analysis.video.platform, analysis.video.id),
				JSON.stringify(analysis),
			);
		},
	};
};
