import { type Note, noteId, notePath, serializeNote } from "./note";
import type { AnswerProvider, SearchProvider } from "./providers";
import { rebuildIndex } from "./search";
import type { Vault } from "./vault";

export async function ask(
	question: string,
	deps: {
		vault: Vault;
		search: SearchProvider;
		model: AnswerProvider;
		now?: () => Date;
	},
): Promise<Note> {
	const sources = await deps.search.search(question);
	const answer = await deps.model.answer(question, sources);
	const created = (deps.now?.() ?? new Date()).toISOString();
	const note: Note = {
		id: noteId(question, created),
		question,
		created,
		model: deps.model.label,
		answer,
		sources,
	};
	await deps.vault.write(notePath(note.id), serializeNote(note));
	await rebuildIndex(deps.vault);
	return note;
}
