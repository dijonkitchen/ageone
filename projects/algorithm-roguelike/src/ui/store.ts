// What the page keeps in this browser: what you learned and your code (meta), and the current run as its
// seed and inputs, so a reload replays it. Storage can be missing (private windows); the game still runs.

export interface Meta {
	unlocked: string[];
	code: Record<string, string>; // passing code-mode source, by concept
	useCode: Record<string, boolean>; // whether that code runs the game
	size: number; // text size in px
}

export interface SavedRun {
	seed: number;
	learned: string[]; // learned before the run began
	inputs: string[];
}

const META = "algorithm-roguelike/meta";
const RUN = "algorithm-roguelike/run";

function read<T>(key: string): T | null {
	try {
		const v = localStorage.getItem(key);
		return v ? (JSON.parse(v) as T) : null;
	} catch {
		return null;
	}
}

function write(key: string, value: unknown) {
	try {
		if (value === null) localStorage.removeItem(key);
		else localStorage.setItem(key, JSON.stringify(value));
	} catch {
		// Storage is full or blocked: the game goes on without saving.
	}
}

export const loadMeta = (): Meta => ({
	unlocked: [],
	code: {},
	useCode: {},
	size: 16,
	...read<Partial<Meta>>(META),
});
export const saveMeta = (m: Meta) => write(META, m);
export const loadRun = () => read<SavedRun>(RUN);
export const saveRun = (r: SavedRun | null) => write(RUN, r);
