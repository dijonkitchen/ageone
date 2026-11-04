// Tile pictures: each pixel coloured by what the tile's geometry says is there, so the picture is the rules.
import { classifier, features } from "./tiles";

export const COLORS = {
	field: [126, 170, 86],
	city: [214, 178, 120],
	wall: [150, 110, 70],
	road: [240, 232, 214],
	junction: [110, 90, 80],
	monastery: [168, 74, 58],
	shield: [52, 92, 170],
} as const;

type Rgb = readonly [number, number, number];

/** RGBA pixels of a tile at rotation 0, `size` pixels square. */
export function tilePixels(code: string, size: number): Uint8ClampedArray {
	const at = classifier(code);
	const out = new Uint8ClampedArray(size * size * 4);
	const kindAt = (x: number, y: number) =>
		at((x + 0.5) / size, (y + 0.5) / size);
	for (let y = 0; y < size; y++)
		for (let x = 0; x < size; x++) {
			const c = kindAt(x, y);
			let rgb: Rgb = COLORS[c.kind];
			// A darker rim where a city meets anything else, so neighbouring cities read as separate.
			if (c.kind === "city")
				for (const [dx, dy] of [
					[1, 0],
					[-1, 0],
					[0, 1],
					[0, -1],
				] as const) {
					const nx = x + dx;
					const ny = y + dy;
					if (nx < 0 || ny < 0 || nx >= size || ny >= size) continue;
					const n = kindAt(nx, ny);
					if (n.kind !== "city" || n.group !== c.group) rgb = COLORS.wall;
				}
			const i = (y * size + x) * 4;
			out[i] = rgb[0];
			out[i + 1] = rgb[1];
			out[i + 2] = rgb[2];
			out[i + 3] = 255;
		}
	// A shield: a small square on the city.
	for (const city of features(code).cities) {
		if (!city.shield) continue;
		const [ax, ay] = city.anchor;
		const r = Math.max(2, Math.round(size * 0.07));
		for (let y = Math.round(ay * size) - r; y <= Math.round(ay * size) + r; y++)
			for (
				let x = Math.round(ax * size) - r;
				x <= Math.round(ax * size) + r;
				x++
			) {
				if (x < 0 || y < 0 || x >= size || y >= size) continue;
				const i = (y * size + x) * 4;
				[out[i], out[i + 1], out[i + 2]] = COLORS.shield;
			}
	}
	return out;
}
