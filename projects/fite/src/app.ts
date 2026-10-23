// The page: reads the controls, runs the game at a fixed 60 steps per second whatever the display's refresh
// rate, plays sounds for what happened, and draws.

import { Sfx } from "./audio";
import { KEYS, keysInput, padInput, TouchPad } from "./controls";
import { newGame, tick } from "./game";
import { Renderer } from "./render";
import { FPS, type Input } from "./sim";

const STEP = 1000 / FPS;
const canvas = document.querySelector("canvas") as HTMLCanvasElement;
const renderer = new Renderer(
	canvas.getContext("2d") as CanvasRenderingContext2D,
);
const game = newGame(Date.now() >>> 0);
const sfx = new Sfx();
const touch = new TouchPad(document.body);
const held = new Set<string>();
const gameKeys = new Set(KEYS.flatMap((m) => Object.keys(m)));

addEventListener("keydown", (e: KeyboardEvent) => {
	sfx.start();
	if (gameKeys.has(e.code)) e.preventDefault();
	held.add(e.code);
});
addEventListener("keyup", (e: KeyboardEvent) => held.delete(e.code));
addEventListener("blur", () => held.clear());
addEventListener("pointerdown", () => sfx.start());

function inputs(): [Input, Input] {
	const pads =
		typeof navigator.getGamepads === "function" ? navigator.getGamepads() : [];
	return [
		keysInput(held, KEYS[0] ?? {}) | padInput(pads[0]) | touch.input(),
		keysInput(held, KEYS[1] ?? {}) | padInput(pads[1]),
	];
}

// What the menus last showed, to click when it changes.
const menuState = () =>
	`${game.screen}|${game.menu}|${game.level}|${game.cursor}|${game.picked}`;
let shown = menuState();

function update(): void {
	tick(game, inputs());
	if (game.screen === "fight" && game.match) {
		renderer.effects(game.match.events);
		for (const e of game.match.events) sfx.play(e.type);
	}
	const now = menuState();
	if (now !== shown && game.screen !== "fight") sfx.play("select");
	shown = now;
}

let last = performance.now();
let behind = 0;
function frame(now: number): void {
	behind = Math.min(behind + now - last, STEP * 5);
	last = now;
	while (behind >= STEP) {
		update();
		behind -= STEP;
	}
	renderer.draw(game);
	requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

document.addEventListener("visibilitychange", () => {
	if (document.hidden && game.screen === "fight") game.paused = true;
});
