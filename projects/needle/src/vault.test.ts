import { expect, test } from "bun:test";
import { MemoryVault, mirror } from "./vault";
import { crc32, exportVault } from "./zip";

test("mirror copies new and changed notes, not the index", async () => {
	const from = new MemoryVault();
	const to = new MemoryVault();
	await from.write("research/a.md", "one");
	await from.write(".needle/index.json", "{}");
	expect(await mirror(from, to)).toBe(1);
	expect(await mirror(from, to)).toBe(0);
	await from.write("research/a.md", "two");
	expect(await mirror(from, to)).toBe(1);
	expect(await to.list()).toEqual(["research/a.md"]);
});

test("crc32 matches the standard check value", () => {
	expect(crc32(new TextEncoder().encode("123456789")).toString(16)).toBe(
		"cbf43926",
	);
});

test("the zip export is a valid archive holding the notes", async () => {
	const vault = new MemoryVault();
	await vault.write("research/a.md", "hello");
	await vault.write(".needle/index.json", "{}");
	const bytes = await exportVault(vault);
	const text = new TextDecoder().decode(bytes);
	expect(text.startsWith("PK\u0003\u0004")).toBe(true);
	expect(text).toContain("research/a.md");
	expect(text).not.toContain("index.json");
	const path = `${import.meta.dir}/../.zip-test.zip`;
	await Bun.write(path, bytes);
	const proc = Bun.spawnSync([
		"python3",
		"-c",
		`import zipfile,sys;z=zipfile.ZipFile(sys.argv[1]);assert z.testzip() is None;print(z.read('research/a.md').decode())`,
		path,
	]);
	await Bun.file(path).delete();
	expect(proc.stdout.toString().trim()).toBe("hello");
});
