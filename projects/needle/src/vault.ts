// The vault is the database: plain files in a folder. MemoryVault is for tests; OpfsVault is the browser's private file system.
export interface Vault {
	list(): Promise<string[]>;
	read(path: string): Promise<string | undefined>;
	write(path: string, content: string): Promise<void>;
	remove(path: string): Promise<void>;
}

export class MemoryVault implements Vault {
	files = new Map<string, string>();
	async list() {
		return [...this.files.keys()].sort();
	}
	async read(path: string) {
		return this.files.get(path);
	}
	async write(path: string, content: string) {
		this.files.set(path, content);
	}
	async remove(path: string) {
		this.files.delete(path);
	}
}

// Any FileSystemDirectoryHandle: the origin-private one, or a folder the user picked to mirror to.
export class DirectoryVault implements Vault {
	constructor(private root: FileSystemDirectoryHandle) {}

	private async dir(parts: string[], create: boolean) {
		let dir = this.root;
		for (const part of parts)
			dir = await dir.getDirectoryHandle(part, { create });
		return dir;
	}

	async list(): Promise<string[]> {
		const out: string[] = [];
		const walk = async (dir: FileSystemDirectoryHandle, prefix: string) => {
			for await (const [name, handle] of dir.entries()) {
				if (handle.kind === "directory")
					await walk(handle as FileSystemDirectoryHandle, `${prefix}${name}/`);
				else out.push(`${prefix}${name}`);
			}
		};
		await walk(this.root, "");
		return out.sort();
	}

	async read(path: string) {
		const parts = path.split("/");
		try {
			const dir = await this.dir(parts.slice(0, -1), false);
			const file = await (
				await dir.getFileHandle(parts.at(-1) ?? "")
			).getFile();
			return await file.text();
		} catch (e) {
			if (e instanceof DOMException && e.name === "NotFoundError")
				return undefined;
			throw e;
		}
	}

	async write(path: string, content: string) {
		const parts = path.split("/");
		const dir = await this.dir(parts.slice(0, -1), true);
		const handle = await dir.getFileHandle(parts.at(-1) ?? "", {
			create: true,
		});
		const writable = await handle.createWritable();
		await writable.write(content);
		await writable.close();
	}

	async remove(path: string) {
		const parts = path.split("/");
		try {
			const dir = await this.dir(parts.slice(0, -1), false);
			await dir.removeEntry(parts.at(-1) ?? "");
		} catch (e) {
			if (!(e instanceof DOMException && e.name === "NotFoundError")) throw e;
		}
	}
}

export async function opfsVault(): Promise<Vault> {
	const root = await navigator.storage.getDirectory();
	return new DirectoryVault(
		await root.getDirectoryHandle("vault", { create: true }),
	);
}

// Copy every file the mirror lacks or holds differently; returns how many were written.
export async function mirror(from: Vault, to: Vault): Promise<number> {
	let written = 0;
	for (const path of await from.list()) {
		if (path.startsWith(".needle/")) continue;
		const content = await from.read(path);
		if (content === undefined || (await to.read(path)) === content) continue;
		await to.write(path, content);
		written++;
	}
	return written;
}
