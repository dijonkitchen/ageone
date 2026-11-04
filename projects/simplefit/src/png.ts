// A minimal 8-bit RGBA PNG encoder for the home screen icons the build draws (iOS wants PNG, not SVG).
import { deflateSync } from "node:zlib";

const CRC = Array.from({ length: 256 }, (_, n) => {
	let c = n;
	for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
	return c >>> 0;
});

function crc32(bytes: Uint8Array): number {
	let c = 0xffffffff;
	for (const b of bytes) c = (CRC[(c ^ b) & 0xff] as number) ^ (c >>> 8);
	return (c ^ 0xffffffff) >>> 0;
}

function chunk(type: string, data: Uint8Array): Buffer {
	const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
	const out = Buffer.alloc(body.length + 8);
	out.writeUInt32BE(data.length, 0);
	body.copy(out, 4);
	out.writeUInt32BE(crc32(body), body.length + 4);
	return out;
}

export function encodePng(
	width: number,
	height: number,
	rgba: Uint8Array,
): Buffer {
	const head = Buffer.alloc(13);
	head.writeUInt32BE(width, 0);
	head.writeUInt32BE(height, 4);
	head.set([8, 6, 0, 0, 0], 8);
	const raw = Buffer.alloc((width * 4 + 1) * height);
	for (let y = 0; y < height; y++)
		raw.set(
			rgba.subarray(y * width * 4, (y + 1) * width * 4),
			y * (width * 4 + 1) + 1,
		);
	return Buffer.concat([
		Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
		chunk("IHDR", head),
		chunk("IDAT", deflateSync(raw)),
		chunk("IEND", new Uint8Array()),
	]);
}

/** The app icon at `size` pixels: icon.svg's pulse line, white on green, drawn with 4x supersampling. */
export function icon(size: number): Uint8Array {
	const points = [
		[10, 34],
		[22, 34],
		[27, 22],
		[34, 46],
		[40, 30],
		[44, 34],
		[54, 34],
	] as const;
	const out = new Uint8Array(size * size * 4);
	const near = (x: number, y: number) => {
		for (let i = 1; i < points.length; i++) {
			const [ax, ay] = points[i - 1] as readonly [number, number];
			const [bx, by] = points[i] as readonly [number, number];
			const t = Math.max(
				0,
				Math.min(
					1,
					((x - ax) * (bx - ax) + (y - ay) * (by - ay)) /
						((bx - ax) ** 2 + (by - ay) ** 2),
				),
			);
			if (Math.hypot(x - ax - t * (bx - ax), y - ay - t * (by - ay)) <= 2.5)
				return true;
		}
		return false;
	};
	for (let py = 0; py < size; py++)
		for (let px = 0; px < size; px++) {
			let hits = 0;
			for (let s = 0; s < 16; s++)
				if (
					near(
						((px + ((s % 4) + 0.5) / 4) * 64) / size,
						((py + (Math.floor(s / 4) + 0.5) / 4) * 64) / size,
					)
				)
					hits++;
			const a = hits / 16;
			const i = (py * size + px) * 4;
			out.set(
				[
					Math.round(11 + (255 - 11) * a),
					Math.round(122 + (255 - 122) * a),
					Math.round(90 + (255 - 90) * a),
					255,
				],
				i,
			);
		}
	return out;
}
