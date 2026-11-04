// The shapes shared by the engine and the concepts. A concept plugs into the game only through `Hooks`,
// so adding one is adding a folder under src/concepts/ and a line in its index, never an engine change.
import type { Floor, Point } from "./grid";
import type { Rng } from "./rng";

export type ItemKind =
	| "healing potion"
	| "dart"
	| "haste potion"
	| "vigor amulet"
	| "page";

export interface FloorItem {
	x: number;
	y: number;
	kind: ItemKind;
	concept?: string; // for a codex page
}

export interface Monster {
	id: number;
	kind: string;
	x: number;
	y: number;
	hp: number;
}

export interface Stack {
	kind: ItemKind;
	count: number;
}

export interface State {
	version: 1;
	seed: number;
	rng: number; // the run's generator state
	depth: number;
	turn: number; // player actions taken
	time: number; // the scheduler's clock, in ticks (a speed-100 action takes 100)
	seq: number; // tie-breaker for the scheduler
	nextId: number;
	unlocked: string[];
	pages: string[]; // codex pages carried, not yet learned
	floor: Floor;
	player: {
		x: number;
		y: number;
		hp: number;
		maxHp: number;
		haste: number;
		hasteBank: number;
	};
	monsters: Monster[];
	items: FloorItem[];
	inventory: Stack[];
	sched: [number, number, number][] | null; // a binary heap of [time, seq, actor id]; actor 0 is the player
	undo: { used: boolean; stack: string[] };
	visible: number[]; // cell indices the player sees now
	log: string[];
	over: boolean;
}

/** What hooks can use: the run's random numbers, the concepts unlocked, and player code when switched on. */
export interface Ctx {
	rng: Rng;
	has(concept: string): boolean;
	/** The player's code for `name` when they switched it on, else the reference. */
	code<F extends (...args: never[]) => unknown>(
		name: string,
		reference: F,
		valid?: (result: unknown) => boolean,
	): F;
	say(message: string): void;
}

/** A new floor, with its stairs and shrine already placed, and where the player starts. */
export interface Generated {
	floor: Floor;
	start: Point;
}

export interface Hooks {
	/** Builds floors; the unlocked generator with the highest priority wins. */
	generator?: {
		priority: number;
		generate(ctx: Ctx, depth: number): Generated;
	};
	/** Adds cells the player sees; every unlocked provider's cells are seen. */
	vision?: (ctx: Ctx, s: State) => Iterable<number>;
	/** Remembers seen cells between turns (fog of war); without it only what is visible now shows. */
	memory?: boolean;
	/** Runs everyone else until it is the player's turn again; the highest priority wins. */
	scheduler?: {
		priority: number;
		afterPlayer(
			ctx: Ctx,
			s: State,
			act: (id: number) => void,
			cost: number,
		): void;
	};
	/** Chooses a monster's next step; the highest priority wins. */
	brain?: {
		priority: number;
		step(ctx: Ctx, s: State, m: Monster): Point | null;
	};
	/** Rolls loot; the highest priority wins. */
	loot?: { priority: number; roll(ctx: Ctx, depth: number): ItemKind };
	/** How the pack holds items; the highest priority wins. */
	inventory?: { priority: number; stacks: boolean; limit: number };
	/** Page features the concept turns on, by name (for example "seeds": seed entry, daily runs, and replays). */
	features?: string[];
	/** Player actions by input name (`act:<name>`); each returns whether it took a turn. */
	actions?: Record<
		string,
		{
			key: string;
			label: string;
			run(ctx: Ctx, s: State, arg?: string): boolean;
		}
	>;
}

/** One picture in a lesson or the sandbox: a drawing, what the data structures hold, and a caption. */
export interface Frame {
	caption: string;
	lines: string[];
	data: string[];
}

export interface PuzzleStep {
	prompt: string;
	lines?: string[];
	choices: string[];
	answer: number; // index into choices, from the reference implementation
	explain: string;
}

export interface Puzzle {
	intro: string;
	steps: PuzzleStep[];
	/** Mistakes allowed while still passing. */
	slack: number;
}

/** A test in a code-mode suite: calls the player's functions and returns a failure message or null. */
export interface TestCase {
	name: string;
	run(call: (fn: string, ...args: unknown[]) => unknown): string | null;
}

export interface CodeTrial {
	exports: string[];
	docs: string;
	starter: string;
	suite: TestCase[];
	budgetMs: number; // the whole suite's time budget
	/** Self-contained reference functions; the suite must pass with them, in and out of the sandbox. */
	reference: Record<string, (...args: never[]) => unknown>;
}

export interface Concept {
	id: string;
	name: string;
	tier: 1 | 2 | 3 | 4;
	requires: string[];
	unlocks: string; // the in-game effect, shown on the codex page before it is learned
	complexity: { time: string; space: string };
	reading: { title: string; url: string };
	lesson: { text: string[]; frames(seed: number): Frame[] };
	puzzle(seed: number): Puzzle;
	hooks: Hooks;
	code?: CodeTrial;
	/** Runs the algorithm on any floor, for the sandbox. */
	sandbox?: (floor: Floor, from: Point, seed: number) => Frame[];
}
