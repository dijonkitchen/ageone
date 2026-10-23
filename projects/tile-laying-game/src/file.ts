// The game file: one plain JSON file with the tile set, the seed, the moves, and a snapshot of the state.
import {
	apply,
	checkState,
	type Move,
	newGame,
	type Player,
	type State,
} from "./engine";

export const FORMAT = "tile-laying-game/1";

export interface GameFile {
	format: typeof FORMAT;
	seed: number | null; // null for a hand-made tile set
	tiles: string[]; // the whole set: the start tile, then the draw order
	starter: Player;
	moves: Move[];
	state: State;
}

export interface Game {
	seed: number | null;
	tiles: string[];
	moves: Move[];
	state: State;
}

export function start(
	tiles: string[],
	seed: number | null,
	starter: Player = 0,
): Game {
	return { seed, tiles, moves: [], state: newGame(tiles, starter) };
}

/** Play a move, or return why it is illegal. */
export function play(game: Game, move: Move): Game | string {
	const state = apply(game.state, move);
	if (typeof state === "string") return state;
	return { ...game, moves: [...game.moves, move], state };
}

export function save(game: Game): string {
	const file: GameFile = {
		format: FORMAT,
		seed: game.seed,
		tiles: game.tiles,
		starter: game.state.starter,
		moves: game.moves,
		state: game.state,
	};
	return `${JSON.stringify(file, null, "\t")}\n`;
}

/** Same JSON whatever the key order, so a hand-written file compares equal to a computed state. */
function stable(v: unknown): string {
	if (Array.isArray(v)) return `[${v.map(stable).join(",")}]`;
	if (v && typeof v === "object")
		return `{${Object.keys(v)
			.sort()
			.map(
				(k) =>
					`${JSON.stringify(k)}:${stable((v as Record<string, unknown>)[k])}`,
			)
			.join(",")}}`;
	return JSON.stringify(v);
}

/**
 * Read a game file. With moves, replaying them from the tile set must give the snapshot.
 * With a snapshot and no moves, the snapshot is the position (for tests or puzzles).
 */
export function load(text: string): Game {
	let file: GameFile;
	try {
		file = JSON.parse(text);
	} catch {
		throw new Error("not a JSON file");
	}
	if (file?.format !== FORMAT) throw new Error(`not a ${FORMAT} game file`);
	if (!Array.isArray(file.tiles) || !Array.isArray(file.moves))
		throw new Error("the file needs tiles and moves lists");
	if (file.starter !== 0 && file.starter !== 1)
		throw new Error("starter must be 0 or 1");
	let game = start(file.tiles, file.seed ?? null, file.starter);
	if (file.moves.length === 0 && file.state) {
		const state = withDefaults(file.state, file.starter);
		const problem = checkState(state);
		if (problem)
			throw new Error(`the snapshot is not a valid position: ${problem}`);
		return { ...game, state };
	}
	for (const [i, move] of file.moves.entries()) {
		const next = play(game, move);
		if (typeof next === "string")
			throw new Error(`move ${i + 1} is illegal: ${next}`);
		game = next;
	}
	if (
		file.state &&
		stable(withDefaults(file.state, file.starter)) !== stable(game.state)
	)
		throw new Error("replaying the moves doesn't give the saved state");
	return game;
}

/** A hand-written snapshot may leave out the parts that are empty at its position. */
function withDefaults(s: Partial<State>, starter: Player): State {
	return {
		board: s.board ?? [],
		meeples: s.meeples ?? [],
		scores: s.scores ?? [0, 0],
		hands: s.hands ?? [null, null],
		deck: s.deck ?? [],
		discards: s.discards ?? [],
		turn: s.turn ?? starter,
		starter: s.starter ?? starter,
		over: s.over ?? false,
	};
}
