// Minimal PNG encoding and decoding for 8-bit RGBA images, for the committed sprite sheet. Used by the sheet
// script and tests (it needs node:zlib), never by the page.

import { deflateSync, inflateSync } from "node:zlib";
import type { Pixels } from "./pixels";

const SIGNATURE = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
	let c = n;
	for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
	return c >>> 0;
});

function crc32(bytes: Uint8Array): number {
	let c = 0xffffffff;
	for (const b of bytes) c = (CRC_TABLE[(c ^ b) & 0xff] as number) ^ (c >>> 8);
	return (c ^ 0xffffffff) >>> 0;
}

function chunk(type: string, data: Uint8Array): Buffer {
	const head = Buffer.alloc(8);
	head.writeUInt32BE(data.length, 0);
	head.write(type, 4, "ascii");
	const crc = Buffer.alloc(4);
	crc.writeUInt32BE(crc32(Buffer.concat([head.subarray(4), data])), 0);
	return Buffer.concat([head, data, crc]);
}

export function encodePng(p: Pixels): Buffer {
	const ihdr = Buffer.alloc(13);
	ihdr.writeUInt32BE(p.width, 0);
	ihdr.writeUInt32BE(p.height, 4);
	ihdr.set([8, 6, 0, 0, 0], 8); // 8-bit RGBA, no interlace
	const stride = p.width * 4;
	const raw = Buffer.alloc((stride + 1) * p.height);
	for (let y = 0; y < p.height; y++)
		raw.set(
			p.data.subarray(y * stride, (y + 1) * stride),
			y * (stride + 1) + 1,
		);
	return Buffer.concat([
		SIGNATURE,
		chunk("IHDR", ihdr),
		chunk("IDAT", deflateSync(raw, { level: 9 })),
		chunk("IEND", new Uint8Array()),
	]);
}

/** Decode a PNG this module wrote (8-bit RGBA, filter type 0 on every row). */
export function decodePng(png: Uint8Array): Pixels {
	const buf = Buffer.from(png);
	if (!buf.subarray(0, 8).equals(SIGNATURE)) throw new Error("not a PNG");
	let width = 0;
	let height = 0;
	const idat: Buffer[] = [];
	for (let at = 8; at < buf.length; ) {
		const length = buf.readUInt32BE(at);
		const type = buf.toString("ascii", at + 4, at + 8);
		const data = buf.subarray(at + 8, at + 8 + length);
		if (type === "IHDR") {
			width = data.readUInt32BE(0);
			height = data.readUInt32BE(4);
			if (data[8] !== 8 || data[9] !== 6) throw new Error("not 8-bit RGBA");
		} else if (type === "IDAT") idat.push(data);
		at += length + 12;
	}
	const raw = inflateSync(Buffer.concat(idat));
	const stride = width * 4;
	const data = new Uint8ClampedArray(stride * height);
	for (let y = 0; y < height; y++) {
		if (raw[y * (stride + 1)] !== 0) throw new Error("unsupported PNG filter");
		data.set(
			raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1)),
			y * stride,
		);
	}
	return { width, height, data };
}
