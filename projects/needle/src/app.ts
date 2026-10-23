import { ask } from "./ask";
import { type Note, parseNote } from "./note";
import {
	type AnswerProvider,
	FakeAnswer,
	FakeSearch,
	KagiProxySearch,
	OpenRouterAnswer,
	PastedSearch,
	roleNames,
	type SearchProvider,
} from "./providers";
import { loadIndex, rebuildIndex, search } from "./search";
import { DirectoryVault, mirror, opfsVault } from "./vault";
import { exportVault } from "./zip";

const $ = <T extends HTMLElement>(id: string) =>
	document.getElementById(id) as T;
const SETTINGS = "needle.settings";

type Settings = { key: string; role: string; proxy: string; pasted: string };

function loadSettings(): Settings {
	const fallback = { key: "", role: "default", proxy: "", pasted: "" };
	try {
		return {
			...fallback,
			...JSON.parse(localStorage.getItem(SETTINGS) ?? "{}"),
		};
	} catch {
		return fallback;
	}
}

function providers(s: Settings): {
	search: SearchProvider;
	model: AnswerProvider;
} {
	return {
		search: s.proxy
			? new KagiProxySearch(s.proxy)
			: s.pasted.trim()
				? new PastedSearch(s.pasted)
				: new FakeSearch(),
		model: s.key ? new OpenRouterAnswer(s.role, s.key) : new FakeAnswer(),
	};
}

const status = (text: string) => {
	$("status").textContent = text;
};

function showNote(markdown: string) {
	const note: Note = parseNote(markdown);
	$("note").hidden = false;
	$("note-title").textContent = note.question;
	$("answer").textContent = note.answer;
	$("markdown").textContent = markdown;
	const list = $("sources");
	list.replaceChildren();
	note.sources.forEach((s, i) => {
		const li = document.createElement("li");
		li.id = `fn-${i + 1}`;
		const a = document.createElement("a");
		a.textContent = s.title;
		if (/^https?:\/\//.test(s.url)) a.href = s.url;
		a.rel = "noopener noreferrer";
		li.append(a, ` — ${s.snippet}`);
		list.append(li);
	});
}

async function main() {
	const vault = await opfsVault();
	const settings = loadSettings();
	const roleSelect = $<HTMLSelectElement>("role");
	for (const role of roleNames()) roleSelect.add(new Option(role, role));
	roleSelect.value = settings.role;
	$<HTMLInputElement>("key").value = settings.key;
	$<HTMLInputElement>("proxy").value = settings.proxy;
	$<HTMLTextAreaElement>("pasted").value = settings.pasted;

	const mode = () => {
		const p = providers(loadSettings());
		$("mode").textContent = `${p.search.constructor.name} + ${p.model.label}`;
	};
	mode();

	let index = await loadIndex(vault);
	const renderList = async (query = "") => {
		const paths = query.trim()
			? search(index, query)
			: (await vault.list()).filter((p) => p.startsWith("research/")).reverse();
		const ul = $("notes");
		ul.replaceChildren();
		for (const path of paths) {
			const markdown = await vault.read(path);
			if (!markdown) continue;
			const li = document.createElement("li");
			const b = document.createElement("button");
			b.type = "button";
			b.textContent = parseNote(markdown).question;
			b.addEventListener("click", () => showNote(markdown));
			li.append(b);
			ul.append(li);
		}
	};
	await renderList();

	$("ask-form").addEventListener("submit", async (e) => {
		e.preventDefault();
		const question = $<HTMLInputElement>("question").value.trim();
		if (!question) return;
		status("Searching and answering…");
		try {
			const p = providers(loadSettings());
			const note = await ask(question, { vault, ...p });
			index = await loadIndex(vault);
			const path = `research/${note.id}.md`;
			showNote((await vault.read(path)) ?? "");
			await renderList();
			status(`Saved ${path}`);
		} catch (err) {
			status(`Failed: ${err instanceof Error ? err.message : String(err)}`);
		}
	});

	$("library-search").addEventListener("input", (e) =>
		renderList((e.target as HTMLInputElement).value),
	);

	$("save").addEventListener("click", () => {
		const next: Settings = {
			key: $<HTMLInputElement>("key").value.trim(),
			role: roleSelect.value,
			proxy: $<HTMLInputElement>("proxy").value.trim(),
			pasted: $<HTMLTextAreaElement>("pasted").value,
		};
		localStorage.setItem(SETTINGS, JSON.stringify(next));
		mode();
		status("Settings saved");
	});

	$("export").addEventListener("click", async () => {
		const bytes = await exportVault(vault);
		const a = document.createElement("a");
		a.href = URL.createObjectURL(
			new Blob([bytes as BlobPart], { type: "application/zip" }),
		);
		a.download = "needle-vault.zip";
		a.click();
		URL.revokeObjectURL(a.href);
		status("Exported needle-vault.zip");
	});

	const picker = (
		window as unknown as {
			showDirectoryPicker?: () => Promise<FileSystemDirectoryHandle>;
		}
	).showDirectoryPicker;
	if (!picker) {
		$("mirror").textContent = "Mirror unavailable here: use Export zip";
		($("mirror") as HTMLButtonElement).disabled = true;
	} else {
		$("mirror").addEventListener("click", async () => {
			try {
				const handle = await picker.call(window);
				const n = await mirror(vault, new DirectoryVault(handle));
				status(`Mirrored ${n} note${n === 1 ? "" : "s"}`);
			} catch (err) {
				status(
					`Mirror failed: ${err instanceof Error ? err.message : String(err)}`,
				);
			}
		});
	}

	// Test hook: lets the end-to-end tests drop the index to prove it rebuilds from the vault.
	(window as unknown as { needle: unknown }).needle = {
		rebuildIndex: () => rebuildIndex(vault),
	};

	if ("serviceWorker" in navigator)
		navigator.serviceWorker.register("sw.js").catch(() => {});
}

main();
