// Keyboard, gamepad, and touch, each turned into the same `Input` bitmask the simulation reads.
// The mappings are pure functions; `TouchPad` is the only part that touches the DOM.

import {
	DOWN,
	type Input,
	KICK,
	LEFT,
	PUNCH,
	RIGHT,
	SPECIAL,
	START,
	UP,
} from "./sim";

/** Key codes (KeyboardEvent.code) for each player. */
export const KEYS: readonly Record<string, Input>[] = [
	{
		KeyW: UP,
		KeyS: DOWN,
		KeyA: LEFT,
		KeyD: RIGHT,
		KeyF: PUNCH,
		KeyG: KICK,
		KeyH: SPECIAL,
		Space: PUNCH,
		Enter: START,
		Escape: START,
	},
	{
		ArrowUp: UP,
		ArrowDown: DOWN,
		ArrowLeft: LEFT,
		ArrowRight: RIGHT,
		KeyK: PUNCH,
		KeyL: KICK,
		Semicolon: SPECIAL,
		Numpad1: PUNCH,
		Numpad2: KICK,
		Numpad3: SPECIAL,
		NumpadEnter: START,
	},
];

export function keysInput(
	held: ReadonlySet<string>,
	map: Record<string, Input>,
): Input {
	let input = 0;
	for (const code of held) input |= map[code] ?? 0;
	return clean(input);
}

/** Opposite directions cancel, as on a real stick. */
export function clean(input: Input): Input {
	let out = input;
	if ((out & (LEFT | RIGHT)) === (LEFT | RIGHT)) out &= ~(LEFT | RIGHT);
	if ((out & (UP | DOWN)) === (UP | DOWN)) out &= ~(UP | DOWN);
	return out;
}

/** The parts of a Gamepad this reads, so tests can pass plain objects. */
export interface PadState {
	axes: readonly number[];
	buttons: readonly { pressed: boolean }[];
}

const DEADZONE = 0.45;
// Standard mapping: 0 A, 1 B, 2 X, 3 Y, 9 Start, 12-15 the d-pad.
const PAD_BUTTONS: [number, Input][] = [
	[0, PUNCH],
	[2, PUNCH],
	[1, KICK],
	[3, SPECIAL],
	[5, SPECIAL],
	[9, START],
	[12, UP],
	[13, DOWN],
	[14, LEFT],
	[15, RIGHT],
];

export function padInput(pad: PadState | null | undefined): Input {
	if (!pad) return 0;
	let input = 0;
	for (const [i, bit] of PAD_BUTTONS) if (pad.buttons[i]?.pressed) input |= bit;
	const [x = 0, y = 0] = pad.axes;
	if (x < -DEADZONE) input |= LEFT;
	if (x > DEADZONE) input |= RIGHT;
	if (y < -DEADZONE) input |= UP;
	if (y > DEADZONE) input |= DOWN;
	return clean(input);
}

/** Directions from a touch at (dx, dy) relative to the d-pad's centre, in the pad's radii. */
export function stickInput(dx: number, dy: number): Input {
	const r = Math.hypot(dx, dy);
	if (r < 0.25) return 0;
	const angle = Math.atan2(dy, dx); // 0 is right, positive is down
	const near = (a: number) =>
		Math.abs(Math.atan2(Math.sin(angle - a), Math.cos(angle - a))) <
		(3 * Math.PI) / 8;
	let input = 0;
	if (near(0)) input |= RIGHT;
	if (near(Math.PI)) input |= LEFT;
	if (near(Math.PI / 2)) input |= DOWN;
	if (near(-Math.PI / 2)) input |= UP;
	return input;
}

/** On-screen d-pad and buttons for touch screens, driving player 1. */
export class TouchPad {
	private readonly held = new Map<number, Input>();
	private tapped: Input = 0; // presses shorter than a frame still count once
	readonly root: HTMLElement;

	constructor(parent: HTMLElement) {
		this.root = document.createElement("div");
		this.root.className = "touch";
		this.root.hidden = true;
		const stick = this.control("stick", "", 0);
		stick.addEventListener("pointermove", (e) => this.aim(stick, e));
		stick.addEventListener("pointerdown", (e) => this.aim(stick, e));
		const buttons = document.createElement("div");
		buttons.className = "buttons";
		for (const [label, bit] of [
			["P", PUNCH],
			["K", KICK],
			["S", SPECIAL],
		] as const)
			buttons.append(this.control("button", label, bit));
		const start = this.control("start", "START", START);
		this.root.append(stick, buttons, start);
		parent.append(this.root);
		window.addEventListener("touchstart", () => this.show(), {
			once: true,
			passive: true,
		});
	}

	show(): void {
		this.root.hidden = false;
	}

	private control(kind: string, label: string, bit: Input): HTMLElement {
		const el = document.createElement("div");
		el.className = kind;
		el.textContent = label;
		el.addEventListener("pointerdown", (e) => {
			e.preventDefault();
			el.setPointerCapture(e.pointerId);
			if (bit) {
				this.held.set(e.pointerId, bit);
				this.tapped |= bit;
			}
		});
		for (const type of ["pointerup", "pointercancel", "lostpointercapture"])
			el.addEventListener(type, (e) =>
				this.held.delete((e as PointerEvent).pointerId),
			);
		return el;
	}

	private aim(stick: HTMLElement, e: PointerEvent): void {
		if (!stick.hasPointerCapture(e.pointerId)) return;
		const box = stick.getBoundingClientRect();
		const r = box.width / 2;
		this.held.set(
			e.pointerId,
			stickInput((e.clientX - box.left - r) / r, (e.clientY - box.top - r) / r),
		);
	}

	input(): Input {
		let input = this.tapped;
		this.tapped = 0;
		for (const bit of this.held.values()) input |= bit;
		return clean(input);
	}
}
