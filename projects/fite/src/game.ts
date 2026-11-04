// Screens around the fight: title, fighter select, the 1P tournament bracket, versus, results, continue, and the
// ending. Pure apart from the seeded generator, so a whole tournament can be played in a test.

import { Cpu, LEVELS, type Level } from "./cpu";
import { BOSS, FIGHTERS, type FighterDef, PLAYABLE } from "./fighters";
import { type Rng, rng, shuffle } from "./rng";
import {
	DOWN,
	FPS,
	type Input,
	KICK,
	LEFT,
	type Match,
	newMatch,
	PUNCH,
	RIGHT,
	type Side,
	START,
	step,
	UP,
} from "./sim";

export type Mode = "tournament" | "versus";
export type Screen =
	| "title"
	| "select"
	| "vs"
	| "fight"
	| "result"
	| "continue"
	| "champion";

export const MENU = ["1P TOURNAMENT", "2P VERSUS", "CPU"] as const;
export const VS_FRAMES = 150;
export const CONTINUE_SECONDS = 10;

export interface Game {
	screen: Screen;
	t: number; // frames on this screen
	menu: number;
	level: Level;
	mode: Mode;
	cursor: [number, number];
	picked: [boolean, boolean];
	bracket: FighterDef[]; // 1P opponents in order, the boss last
	stage: number; // index into the bracket
	match: Match | null;
	paused: boolean;
	cpu: Cpu | null; // player 2's CPU in a tournament
	random: Rng;
	prev: [Input, Input];
}

export function newGame(seed: number): Game {
	return {
		screen: "title",
		t: 0,
		menu: 0,
		level: "normal",
		mode: "tournament",
		cursor: [0, 1],
		picked: [false, false],
		bracket: [],
		stage: 0,
		match: null,
		paused: false,
		cpu: null,
		random: rng(seed),
		prev: [0, 0],
	};
}

const CONFIRM = PUNCH | START;
const BACK = KICK;

function go(g: Game, screen: Screen): void {
	g.screen = screen;
	g.t = 0;
}

/** The two fighters of the next fight. */
export function fighters(g: Game): [FighterDef, FighterDef] {
	const p1 = PLAYABLE[g.cursor[0]] as FighterDef;
	if (g.mode === "tournament") return [p1, g.bracket[g.stage] as FighterDef];
	return [p1, PLAYABLE[g.cursor[1]] as FighterDef];
}

/** Index into STAGES for this fight: the opponent's home stage. */
export const stageOf = (g: Game): number => FIGHTERS.indexOf(fighters(g)[1]);

function startFight(g: Game): void {
	const [a, b] = fighters(g);
	g.match = newMatch(a, b);
	g.cpu =
		g.mode === "tournament"
			? new Cpu(g.level, Math.floor(g.random() * 2 ** 31))
			: null;
	g.paused = false;
	go(g, "vs");
}

function title(g: Game, pressed: Input): void {
	if (pressed & UP) g.menu = (g.menu + MENU.length - 1) % MENU.length;
	if (pressed & DOWN) g.menu = (g.menu + 1) % MENU.length;
	if (g.menu === 2 && pressed & (LEFT | RIGHT | CONFIRM)) {
		const by = pressed & LEFT ? -1 : 1;
		g.level = LEVELS[
			(LEVELS.indexOf(g.level) + by + LEVELS.length) % LEVELS.length
		] as Level;
		return;
	}
	if (pressed & CONFIRM) {
		g.mode = g.menu === 0 ? "tournament" : "versus";
		g.picked = [false, false];
		go(g, "select");
	}
}

function select(g: Game, pressed: [Input, Input]): void {
	const players: Side[] = g.mode === "versus" ? [0, 1] : [0];
	for (const side of players) {
		const p = pressed[side];
		if (g.picked[side]) {
			if (p & BACK) g.picked[side] = false;
			continue;
		}
		const n = PLAYABLE.length;
		if (p & LEFT) g.cursor[side] = (g.cursor[side] + n - 1) % n;
		if (p & RIGHT) g.cursor[side] = (g.cursor[side] + 1) % n;
		if (p & CONFIRM) g.picked[side] = true;
		else if (p & BACK && side === 0) {
			go(g, "title");
			return;
		}
	}
	if (players.every((s) => g.picked[s])) {
		if (g.mode === "tournament") {
			const me = PLAYABLE[g.cursor[0]];
			g.bracket = [
				...shuffle(
					PLAYABLE.filter((f) => f !== me),
					g.random,
				),
				BOSS,
			];
			g.stage = 0;
		}
		startFight(g);
	}
}

function result(g: Game, pressed: Input): void {
	const m = g.match as Match;
	// Show the result for a second, then go on at a press or after four.
	if (g.t < FPS || (!(pressed & CONFIRM) && g.t < 4 * FPS)) return;
	if (g.mode === "versus") {
		g.picked = [false, false];
		go(g, "select");
	} else if (m.result === 0 && g.stage === g.bracket.length - 1)
		go(g, "champion");
	else if (m.result === 0) {
		g.stage++;
		startFight(g);
	} else if (m.result === "draw") startFight(g);
	else go(g, "continue");
}

/**
 * Advance the game one frame. `inputs` are the two players' held buttons (player 2's are ignored in a
 * tournament, where the CPU plays that side). Mutates and returns the game.
 */
export function tick(g: Game, inputs: readonly [Input, Input]): Game {
	const pressed: [Input, Input] = [
		inputs[0] & ~g.prev[0],
		inputs[1] & ~g.prev[1],
	];
	g.prev = [inputs[0], inputs[1]];
	g.t++;
	// In a tournament either set of controls drives player 1 in the menus.
	const any =
		g.mode === "tournament" || g.screen === "title"
			? pressed[0] | pressed[1]
			: pressed[0];
	switch (g.screen) {
		case "title":
			title(g, pressed[0] | pressed[1]);
			break;
		case "select":
			select(g, g.mode === "tournament" ? [any, 0] : pressed);
			break;
		case "vs":
			if (g.t >= VS_FRAMES || any & CONFIRM) go(g, "fight");
			break;
		case "fight": {
			const m = g.match as Match;
			if ((pressed[0] | pressed[1]) & START) g.paused = !g.paused;
			if (g.paused) {
				if (any & BACK) go(g, "title");
				break;
			}
			const p2 =
				g.mode === "tournament" ? (g.cpu as Cpu).input(m, 1) : inputs[1];
			const p1 = g.mode === "tournament" ? inputs[0] | inputs[1] : inputs[0];
			step(m, [p1 & ~START, p2 & ~START]);
			if (m.phase === "matchOver") go(g, "result");
			break;
		}
		case "result":
			result(g, any);
			break;
		case "continue":
			if (any & CONFIRM) startFight(g);
			else if (any & BACK || g.t >= CONTINUE_SECONDS * FPS) go(g, "title");
			break;
		case "champion":
			if (g.t > 2 * FPS && any & CONFIRM) go(g, "title");
			break;
	}
	return g;
}
