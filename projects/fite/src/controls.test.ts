import { expect, test } from "bun:test";
import { KEYS, keysInput, padInput, stickInput } from "./controls";
import { eachDot, glyph, textWidth } from "./font";
import { DOWN, KICK, LEFT, PUNCH, RIGHT, SPECIAL, START, UP } from "./sim";

const pad = (pressed: number[], axes = [0, 0]) => ({
	axes,
	buttons: Array.from({ length: 17 }, (_, i) => ({
		pressed: pressed.includes(i),
	})),
});

test("keyboard maps per player, and opposite directions cancel", () => {
	const p1 = KEYS[0] ?? {};
	const p2 = KEYS[1] ?? {};
	expect(keysInput(new Set(["KeyD", "KeyF"]), p1)).toBe(RIGHT | PUNCH);
	expect(keysInput(new Set(["KeyA", "KeyD", "KeyW"]), p1)).toBe(UP);
	expect(keysInput(new Set(["ArrowDown", "KeyL", "Semicolon"]), p2)).toBe(
		DOWN | KICK | SPECIAL,
	);
	expect(keysInput(new Set(["ArrowDown"]), p1)).toBe(0);
});

test("gamepads use the standard mapping: d-pad or stick, A punch, B kick, Y special, Start", () => {
	expect(padInput(pad([0, 9]))).toBe(PUNCH | START);
	expect(padInput(pad([1, 3, 14]))).toBe(KICK | SPECIAL | LEFT);
	expect(padInput(pad([], [0.9, -0.8]))).toBe(RIGHT | UP);
	expect(padInput(pad([], [0.2, 0.3]))).toBe(0);
	expect(padInput(null)).toBe(0);
});

test("the touch stick reads eight directions with a dead zone", () => {
	expect(stickInput(0.1, 0)).toBe(0);
	expect(stickInput(1, 0)).toBe(RIGHT);
	expect(stickInput(0, -1)).toBe(UP);
	expect(stickInput(-0.7, 0.7)).toBe(LEFT | DOWN);
	expect(stickInput(0.7, -0.7)).toBe(RIGHT | UP);
});

test("the pixel font has every character the game writes", () => {
	for (const ch of "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 !?.:-/<>';,")
		expect(glyph(ch)).toHaveLength(5);
	expect(textWidth("AB", 2)).toBe(14);
	const dots: [number, number][] = [];
	eachDot("I", 0, 0, 1, (x, y) => dots.push([x, y]));
	expect(dots).toHaveLength(9);
});
