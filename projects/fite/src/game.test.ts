import { expect, test } from "bun:test";
import { Cpu } from "./cpu";
import { BOSS, PLAYABLE } from "./fighters";
import { type Game, newGame, tick } from "./game";
import { DOWN, type Input, KICK, PUNCH, RIGHT, START } from "./sim";

/** Hold `input` for a frame, then release for a frame, so it registers as one press. */
function tap(g: Game, input: Input, side: 0 | 1 = 0): void {
	tick(g, side === 0 ? [input, 0] : [0, input]);
	tick(g, [0, 0]);
}

test("a whole tournament: pick, three opponents in a random order, the boss, the ending", () => {
	const g = newGame(42);
	tap(g, START);
	expect(g.screen).toBe("select");
	tap(g, RIGHT);
	tap(g, PUNCH);
	expect(g.screen).toBe("vs");
	const me = PLAYABLE[1];
	expect(g.bracket).toHaveLength(4);
	expect(g.bracket.at(-1)).toBe(BOSS);
	expect(new Set(g.bracket.slice(0, 3))).toEqual(
		new Set(PLAYABLE.filter((f) => f !== me)),
	);
	// A hard CPU plays player 1 against the default normal CPU.
	const pilot = new Cpu("hard", 3);
	const met: string[] = [];
	for (let frame = 0; frame < 200_000 && g.screen !== "champion"; frame++) {
		if (g.screen === "vs" && met.at(-1) !== `${g.stage}`)
			met.push(`${g.stage}`);
		if (g.screen === "continue") tap(g, PUNCH);
		else if (g.screen === "fight" && g.match)
			tick(g, [pilot.input(g.match, 0), 0]);
		else tick(g, [0, 0]);
	}
	expect(g.screen).toBe("champion");
	expect(met).toEqual(["0", "1", "2", "3"]);
	tick(g, [0, 0]);
	for (let i = 0; i < 150; i++) tick(g, [0, 0]);
	tap(g, PUNCH);
	expect(g.screen).toBe("title");
});

test("a loss offers a continue, and declining goes back to the title", () => {
	const g = newGame(1);
	tap(g, START);
	tap(g, PUNCH);
	for (let i = 0; i < 100_000 && g.screen !== "continue"; i++) tick(g, [0, 0]);
	expect(g.screen).toBe("continue");
	tap(g, KICK);
	expect(g.screen).toBe("title");
});

test("2P versus: both players pick, and the result goes back to select", () => {
	const g = newGame(5);
	tap(g, DOWN);
	tap(g, PUNCH);
	expect([g.screen, g.mode]).toEqual(["select", "versus"]);
	tap(g, PUNCH, 0);
	expect(g.screen).toBe("select");
	tap(g, RIGHT, 1);
	tap(g, PUNCH, 1);
	expect(g.screen).toBe("vs");
	tap(g, PUNCH);
	expect(g.screen).toBe("fight");
	for (let i = 0; i < 100_000 && g.screen === "fight"; i++) tick(g, [0, 0]);
	expect(g.match?.result).toBe("draw"); // nobody touched anything
	for (let i = 0; i < 300 && g.screen === "result"; i++) tick(g, [0, 0]);
	expect(g.screen).toBe("select");
});

test("start pauses the fight, and the CPU level is picked on the title", () => {
	const g = newGame(9);
	tap(g, DOWN);
	tap(g, DOWN);
	tap(g, RIGHT);
	expect(g.level).toBe("hard");
	tap(g, DOWN);
	tap(g, PUNCH);
	tap(g, PUNCH);
	tap(g, PUNCH);
	expect(g.screen).toBe("fight");
	tap(g, START);
	const frame = g.match?.frame;
	for (let i = 0; i < 30; i++) tick(g, [0, 0]);
	expect(g.match?.frame).toBe(frame);
	tap(g, START);
	tick(g, [0, 0]);
	expect(g.match?.frame).toBeGreaterThan(frame ?? 0);
});
