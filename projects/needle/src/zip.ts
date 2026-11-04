// Minimal store-only zip, for browsers that cannot write to a chosen folder.
const TABLE = (() => {
	const t = new Uint32Array(256);
	for (let n = 0; n < 256; n++) {
		let c = n;
		for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
		t[n] = c >>> 0;
	}
	return t;
})();

export function crc32(data: Uint8Array): number {
	let c = 0xffffffff;
	for (const b of data) c = (TABLE[(c ^ b) & 0xff] ?? 0) ^ (c >>> 8);
	return (c ^ 0xffffffff) >>> 0;
}

export function zip(files: Map<string, string>): Uint8Array {
	const enc = new TextEncoder();
	const chunks: Uint8Array[] = [];
	const central: Uint8Array[] = [];
	let offset = 0;
	const u16 = (v: DataView, o: number, n: number) => v.setUint16(o, n, true);
	const u32 = (v: DataView, o: number, n: number) => v.setUint32(o, n, true);
	for (const [name, content] of files) {
		const nameBytes = enc.encode(name);
		const data = enc.encode(content);
		const crc = crc32(data);
		const local = new Uint8Array(30 + nameBytes.length);
		const lv = new DataView(local.buffer);
		u32(lv, 0, 0x04034b50);
		u16(lv, 4, 20);
		u16(lv, 6, 0x0800); // UTF-8 names
		u32(lv, 14, crc);
		u32(lv, 18, data.length);
		u32(lv, 22, data.length);
		u16(lv, 26, nameBytes.length);
		local.set(nameBytes, 30);
		const entry = new Uint8Array(46 + nameBytes.length);
		const ev = new DataView(entry.buffer);
		u32(ev, 0, 0x02014b50);
		u16(ev, 4, 20);
		u16(ev, 6, 20);
		u16(ev, 8, 0x0800);
		u32(ev, 16, crc);
		u32(ev, 20, data.length);
		u32(ev, 24, data.length);
		u16(ev, 28, nameBytes.length);
		u32(ev, 42, offset);
		entry.set(nameBytes, 46);
		chunks.push(local, data);
		central.push(entry);
		offset += local.length + data.length;
	}
	const size = central.reduce((n, c) => n + c.length, 0);
	const end = new Uint8Array(22);
	const dv = new DataView(end.buffer);
	u32(dv, 0, 0x06054b50);
	u16(dv, 8, files.size);
	u16(dv, 10, files.size);
	u32(dv, 12, size);
	u32(dv, 16, offset);
	const all = [...chunks, ...central, end];
	const out = new Uint8Array(all.reduce((n, c) => n + c.length, 0));
	let at = 0;
	for (const c of all) {
		out.set(c, at);
		at += c.length;
	}
	return out;
}

export async function exportVault(vault: {
	list(): Promise<string[]>;
	read(p: string): Promise<string | undefined>;
}): Promise<Uint8Array> {
	const files = new Map<string, string>();
	for (const path of await vault.list())
		if (!path.startsWith(".needle/"))
			files.set(path, (await vault.read(path)) ?? "");
	return zip(files);
}
