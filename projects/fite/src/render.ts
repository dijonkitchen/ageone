// Draws the game onto a 320x180 canvas, which the page scales up with crisp pixels. Sprites and stages are
// drawn once into offscreen canvases from the pixel buffers; each frame only copies rectangles.

import {
	FIGHTERS,
	type FighterDef,
	METER_MAX,
	PLAYABLE,
	type Rgb,
} from "./fighters";
import { eachDot, textWidth } from "./font";
import { CONTINUE_SECONDS, fighters, type Game, MENU, stageOf } from "./game";
import type { Pixels } from "./pixels";
import {
	type Fighter,
	FPS,
	GROUND,
	HEIGHT,
	type Match,
	ROUNDS_TO_WIN,
	type SimEvent,
	seconds,
	WIDTH,
} from "./sim";
import {
	ANCHOR,
	CELL,
	POSE_NAMES,
	type PoseName,
	poseOf,
	sheet,
} from "./sprites";
import { drawStage, STAGES } from "./stage";

type Ctx = CanvasRenderingContext2D;
type Align = "left" | "center" | "right";

const WHITE: Rgb = [248, 248, 240];
const DARK: Rgb = [16, 12, 24];
const GOLD: Rgb = [255, 208, 64];
const RED: Rgb = [232, 64, 56];
const P1: Rgb = [80, 200, 255];
const P2: Rgb = [255, 112, 96];
const css = (c: Rgb, a = 1) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;

function canvasOf(p: Pixels): HTMLCanvasElement {
	const c = document.createElement("canvas");
	c.width = p.width;
	c.height = p.height;
	const ctx = c.getContext("2d") as Ctx;
	const image = ctx.createImageData(p.width, p.height);
	image.data.set(p.data);
	ctx.putImageData(image, 0, 0);
	return c;
}

interface Spark {
	x: number;
	y: number;
	t: number;
	color: Rgb;
}

export class Renderer {
	private readonly sprites: HTMLCanvasElement;
	private readonly stages: HTMLCanvasElement[];
	private sparks: Spark[] = [];
	private shake = 0;

	constructor(private readonly ctx: Ctx) {
		ctx.imageSmoothingEnabled = false;
		this.sprites = canvasOf(sheet());
		this.stages = STAGES.map((_, i) => canvasOf(drawStage(i)));
	}

	/** Effects for this frame's simulation events. */
	effects(events: readonly SimEvent[]): void {
		for (const e of events) {
			if (e.type === "hit" || e.type === "ko") {
				this.sparks.push({ x: e.x, y: GROUND - e.y, t: 0, color: GOLD });
				this.shake = e.type === "ko" ? 10 : 4;
			} else if (e.type === "block")
				this.sparks.push({ x: e.x, y: GROUND - e.y, t: 0, color: WHITE });
		}
	}

	draw(g: Game): void {
		const ctx = this.ctx;
		ctx.save();
		ctx.fillStyle = css(DARK);
		ctx.fillRect(0, 0, WIDTH, HEIGHT);
		switch (g.screen) {
			case "title":
				this.title(g);
				break;
			case "select":
				this.select(g);
				break;
			case "vs":
				this.versus(g);
				break;
			case "fight":
			case "result":
				this.fight(g);
				break;
			case "continue":
				this.backdrop(stageOf(g));
				this.text("CONTINUE?", WIDTH / 2, 60, 4, GOLD);
				this.text(
					String(Math.max(0, CONTINUE_SECONDS - Math.floor(g.t / FPS))),
					WIDTH / 2,
					92,
					5,
					WHITE,
				);
				this.text(
					"PUNCH TO FIGHT AGAIN   KICK TO QUIT",
					WIDTH / 2,
					150,
					1,
					WHITE,
				);
				break;
			case "champion": {
				this.backdrop(2);
				const me = fighters(g)[0];
				this.sprite(me, "victory", WIDTH / 2, 130, 1, 2);
				this.text("CHAMPION!", WIDTH / 2, 20, 4, GOLD);
				this.text(`${me.name} TAKES THE TOURNAMENT`, WIDTH / 2, 146, 1, WHITE);
				this.text(`ON ${g.level.toUpperCase()}`, WIDTH / 2, 156, 1, WHITE);
				break;
			}
		}
		ctx.restore();
	}

	private backdrop(stage: number, dim = 0.55): void {
		this.ctx.drawImage(
			this.stages[stage % this.stages.length] as HTMLCanvasElement,
			0,
			0,
		);
		this.ctx.fillStyle = css(DARK, dim);
		this.ctx.fillRect(0, 0, WIDTH, HEIGHT);
	}

	private title(g: Game): void {
		this.backdrop(1, 0.4);
		const bob = Math.round(Math.sin(g.t / 20) * 2);
		this.text("SHELL", WIDTH / 2, 18 + bob, 5, GOLD);
		this.text("SHOCK", WIDTH / 2, 48 + bob, 5, RED);
		this.text("A TURTLE NINJA TOURNAMENT", WIDTH / 2, 80, 1, WHITE);
		for (const [i, item] of MENU.entries()) {
			const label = item === "CPU" ? `CPU: ${g.level.toUpperCase()}` : item;
			const on = g.menu === i;
			const y = 98 + i * 14;
			this.text(
				on ? `> ${label} <` : label,
				WIDTH / 2,
				y,
				2,
				on ? GOLD : WHITE,
			);
		}
		this.text(
			"P1  WASD MOVE  F PUNCH  G KICK  H SPECIAL",
			WIDTH / 2,
			152,
			1,
			WHITE,
		);
		this.text(
			"P2  ARROWS  K PUNCH  L KICK  ; SPECIAL",
			WIDTH / 2,
			160,
			1,
			WHITE,
		);
		this.text("ENTER START  OR A GAMEPAD  OR TOUCH", WIDTH / 2, 168, 1, WHITE);
	}

	private select(g: Game): void {
		this.backdrop(0);
		this.text("CHOOSE YOUR FIGHTER", WIDTH / 2, 10, 2, GOLD);
		const gap = WIDTH / PLAYABLE.length;
		for (const [i, f] of PLAYABLE.entries()) {
			const x = gap * i + gap / 2;
			const p1 = g.cursor[0] === i;
			const p2 = g.mode === "versus" && g.cursor[1] === i;
			if (p1 || p2) {
				this.ctx.fillStyle = css(p1 && p2 ? GOLD : p1 ? P1 : P2, 0.35);
				this.ctx.fillRect(x - gap / 2 + 4, 28, gap - 8, 118);
			}
			const picked = (p1 && g.picked[0]) || (p2 && g.picked[1]);
			this.sprite(
				f,
				picked ? "victory" : Math.floor(g.t / 30) % 2 ? "idle1" : "idle0",
				x,
				112,
				1,
				2,
			);
			this.text(f.name, x, 118, 2, WHITE);
			this.text(f.style, x, 134, 1, WHITE);
			if (p1) this.text("P1", x - 18, 32, 1, P1);
			if (p2) this.text("P2", x + 18, 32, 1, P2);
		}
		this.text(
			g.mode === "versus"
				? "BOTH PLAYERS: PUNCH TO PICK"
				: "PUNCH TO PICK   KICK TO GO BACK",
			WIDTH / 2,
			160,
			1,
			WHITE,
		);
	}

	private versus(g: Game): void {
		const [a, b] = fighters(g);
		this.backdrop(stageOf(g));
		this.sprite(a, "idle0", 80, 130, 1, 2);
		this.sprite(b, "idle0", 240, 130, -1, 2);
		this.text(a.name, 80, 138, 2, P1);
		this.text(b.name, 240, 138, 2, P2);
		this.text("VS", WIDTH / 2, 70, 4, GOLD);
		this.text(STAGES[stageOf(g)]?.name ?? "", WIDTH / 2, 160, 1, WHITE);
		if (g.mode === "tournament") {
			const last = g.stage === g.bracket.length - 1;
			this.text(
				last ? "FINAL MATCH" : `MATCH ${g.stage + 1} OF ${g.bracket.length}`,
				WIDTH / 2,
				14,
				2,
				last ? RED : WHITE,
			);
			const names = g.bracket
				.map((f, i) => (i < g.stage ? "-" : f.name))
				.join("  ");
			this.text(names, WIDTH / 2, 30, 1, WHITE);
		}
	}

	private fight(g: Game): void {
		const m = g.match as Match;
		const ctx = this.ctx;
		if (this.shake > 0) {
			ctx.translate(Math.round((Math.random() - 0.5) * this.shake), 0);
			this.shake--;
		}
		ctx.drawImage(this.stages[stageOf(g)] as HTMLCanvasElement, 0, 0);
		for (const f of m.fighters) {
			ctx.fillStyle = css(DARK, 0.35);
			const w = Math.max(6, 18 - f.y / 4);
			ctx.fillRect(Math.round(f.x - w / 2), GROUND - 1, Math.round(w), 2);
		}
		// The fighter acting most recently draws on top.
		const order = [...m.fighters].sort(
			(a, b) => Number(a.action === "attack") - Number(b.action === "attack"),
		);
		for (const f of order) this.fighter(f, m.frame);
		for (const p of m.projectiles) {
			const flicker = Math.floor(p.t / 3) % 2 ? 0 : 1;
			this.disc(p.x, GROUND - p.y, p.def.radius + flicker, [
				...p.def.color,
			] as Rgb);
			this.disc(p.x, GROUND - p.y, p.def.radius / 2, WHITE);
		}
		this.sparks = this.sparks.filter((s) => s.t++ < 10);
		for (const s of this.sparks) {
			const r = 2 + s.t;
			ctx.fillStyle = css(s.color, 1 - s.t / 10);
			for (const [dx, dy] of [
				[1, 0],
				[-1, 0],
				[0, 1],
				[0, -1],
				[0.7, 0.7],
				[-0.7, -0.7],
				[0.7, -0.7],
				[-0.7, 0.7],
			] as const)
				ctx.fillRect(
					Math.round(s.x + dx * r) - 1,
					Math.round(s.y + dy * r) - 1,
					2,
					2,
				);
		}
		this.hud(m);
		this.banner(g, m);
	}

	private fighter(f: Fighter, frame: number): void {
		const flash = f.action === "hitstun" && f.t < 4;
		this.sprite(f.def, poseOf(f, frame), f.x, GROUND - f.y, f.facing, 1, flash);
	}

	private hud(m: Match): void {
		const ctx = this.ctx;
		const bar = 128;
		for (const side of [0, 1] as const) {
			const f = m.fighters[side];
			const x = side === 0 ? 8 : WIDTH - 8 - bar;
			ctx.fillStyle = css(DARK);
			ctx.fillRect(x - 1, 7, bar + 2, 8);
			ctx.fillStyle = css(RED);
			ctx.fillRect(x, 8, bar, 6);
			const w = Math.round((bar * f.health) / f.def.health);
			ctx.fillStyle = css(
				f.health / f.def.health < 0.25 ? GOLD : [96, 220, 96],
			);
			ctx.fillRect(side === 0 ? x + bar - w : x, 8, w, 6);
			this.text(
				f.def.name,
				side === 0 ? x : x + bar,
				17,
				1,
				WHITE,
				side === 0 ? "left" : "right",
			);
			for (let i = 0; i < ROUNDS_TO_WIN; i++) {
				ctx.fillStyle = css(i < m.wins[side] ? GOLD : DARK);
				const px = side === 0 ? x + bar - 6 - i * 7 : x + 2 + i * 7;
				ctx.fillRect(px, 17, 5, 5);
			}
			const meter = Math.round((60 * f.meter) / METER_MAX);
			const mx = side === 0 ? 8 : WIDTH - 68;
			ctx.fillStyle = css(DARK);
			ctx.fillRect(mx - 1, 169, 62, 6);
			ctx.fillStyle = css(f.meter >= METER_MAX / 2 ? P1 : [60, 90, 140]);
			ctx.fillRect(side === 0 ? mx : mx + 60 - meter, 170, meter, 4);
			if (f.meter >= METER_MAX / 2)
				this.text(
					"SPECIAL",
					side === 0 ? mx + 64 : mx - 4,
					169,
					1,
					P1,
					side === 0 ? "left" : "right",
				);
		}
		this.text(
			String(seconds(m)).padStart(2, "0"),
			WIDTH / 2,
			6,
			3,
			seconds(m) <= 10 ? RED : WHITE,
		);
	}

	private banner(g: Game, m: Match): void {
		if (g.paused) {
			this.ctx.fillStyle = css(DARK, 0.6);
			this.ctx.fillRect(0, 0, WIDTH, HEIGHT);
			this.text("PAUSED", WIDTH / 2, 70, 4, GOLD);
			this.text("START TO RESUME   KICK TO QUIT", WIDTH / 2, 104, 1, WHITE);
			return;
		}
		if (m.phase === "intro")
			this.text(`ROUND ${m.round}`, WIDTH / 2, 70, 4, WHITE);
		else if (m.phase === "fight" && m.t < 30)
			this.text("FIGHT!", WIDTH / 2, 70, 4, GOLD);
		else if (m.phase === "roundOver" || m.phase === "matchOver") {
			const ko = m.fighters.some((f) => f.health <= 0);
			if (m.phase === "roundOver" && m.t < 60)
				this.text(ko ? "K.O." : "TIME", WIDTH / 2, 70, 5, RED);
			else {
				const w = m.phase === "matchOver" ? m.result : m.roundWinner;
				const name =
					w === "draw" || w === null
						? "DRAW"
						: `${m.fighters[w].def.name} WINS`;
				this.text(name, WIDTH / 2, 70, 3, GOLD);
				if (g.screen === "result" && g.mode === "tournament")
					this.text(
						m.result === 0
							? "YOU WIN"
							: m.result === 1
								? "YOU LOSE"
								: "REMATCH",
						WIDTH / 2,
						96,
						2,
						WHITE,
					);
			}
		}
	}

	private sprite(
		def: FighterDef,
		pose: PoseName,
		x: number,
		y: number,
		facing: number,
		scale: number,
		flash = false,
	): void {
		const ctx = this.ctx;
		const row = FIGHTERS.indexOf(def);
		const col = POSE_NAMES.indexOf(pose);
		ctx.save();
		ctx.translate(Math.round(x), Math.round(y));
		ctx.scale(facing < 0 ? -scale : scale, scale);
		if (flash) ctx.filter = "brightness(2.2)";
		ctx.drawImage(
			this.sprites,
			col * CELL,
			row * CELL,
			CELL,
			CELL,
			-ANCHOR.x,
			-ANCHOR.y,
			CELL,
			CELL,
		);
		ctx.restore();
	}

	private disc(cx: number, cy: number, r: number, c: Rgb): void {
		this.ctx.fillStyle = css(c);
		for (let dy = -Math.floor(r); dy <= r; dy++) {
			const w = Math.floor(Math.sqrt(r * r - dy * dy));
			this.ctx.fillRect(Math.round(cx - w), Math.round(cy + dy), w * 2 + 1, 1);
		}
	}

	/** Pixel-font text with a one-pixel shadow; `y` is the top. */
	private text(
		s: string,
		x: number,
		y: number,
		scale: number,
		c: Rgb,
		align: Align = "center",
	): void {
		const w = textWidth(s, scale);
		const left = Math.round(
			align === "center" ? x - w / 2 : align === "right" ? x - w : x,
		);
		for (const [color, off] of [
			[DARK, Math.max(1, scale / 2)],
			[c, 0],
		] as const) {
			this.ctx.fillStyle = css(color);
			eachDot(s, left + off, y + off, scale, (dx, dy) =>
				this.ctx.fillRect(dx, dy, scale, scale),
			);
		}
	}
}
