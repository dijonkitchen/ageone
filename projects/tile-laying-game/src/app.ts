// The browser page: draws the game and turns clicks into moves. Every change goes through the rules engine.
import { tilePixels } from "./draw";
import {
	anchorPoint,
	type FeatureRef,
	meeplePoint,
	meepleSpots,
	meeplesLeft,
	type Placed,
	type Player,
	placements,
	winner,
} from "./engine";
import { type Game, load, play, save, start } from "./file";
import { generate } from "./generate";

const NAMES = ["Red", "Blue"] as const;
const PLAYER_COLORS = ["#d8433b", "#2f6fd6"] as const;
const TILE_PX = 96;

const $ = <T extends HTMLElement>(id: string) =>
	document.getElementById(id) as T;
const canvas = $<HTMLCanvasElement>("board");
const ctx = canvas.getContext("2d") as CanvasRenderingContext2D;
const status = $("status");
const message = $("message");

const newSeed = () => Math.floor(Math.random() * 2 ** 31);
const firstSeed = newSeed();
let game: Game = start(generate(firstSeed), firstSeed);
let pick: { x: number; y: number; r: number } | null = null; // where the current tile is being tried
let chosen: FeatureRef | null = null;

function fresh(seed: number, starter: Player) {
	game = start(generate(seed), seed, starter);
	pick = null;
	chosen = null;
	say("");
	render();
}

// Tile pictures, drawn once per code.
const images = new Map<string, HTMLCanvasElement>();
function image(code: string): HTMLCanvasElement {
	let c = images.get(code);
	if (!c) {
		c = document.createElement("canvas");
		c.width = c.height = TILE_PX;
		const data = new ImageData(TILE_PX, TILE_PX);
		data.data.set(tilePixels(code, TILE_PX));
		(c.getContext("2d") as CanvasRenderingContext2D).putImageData(data, 0, 0);
		images.set(code, c);
	}
	return c;
}

function drawTile(
	g: CanvasRenderingContext2D,
	code: string,
	px: number,
	py: number,
	size: number,
	r: number,
	alpha = 1,
) {
	g.save();
	g.globalAlpha = alpha;
	g.translate(px + size / 2, py + size / 2);
	g.rotate((r * Math.PI) / 2);
	g.drawImage(image(code), -size / 2, -size / 2, size, size);
	g.restore();
}

function drawMeeple(
	g: CanvasRenderingContext2D,
	x: number,
	y: number,
	size: number,
	player: Player,
	ghost = false,
) {
	g.beginPath();
	g.arc(x, y, size * 0.09, 0, Math.PI * 2);
	g.fillStyle = ghost ? "rgba(255,255,255,0.65)" : PLAYER_COLORS[player];
	g.fill();
	g.lineWidth = Math.max(1.5, size * 0.025);
	g.strokeStyle = ghost ? PLAYER_COLORS[player] : "#fff";
	g.stroke();
}

// The view: the board's bounds plus a margin of one cell, fitted into the canvas.
let view = { cell: 64, ox: 0, oy: 0 };

function layout() {
	const s = game.state;
	const spots = placements(s);
	const xs = [...s.board.map((t) => t.x), ...spots.map((p) => p.x)];
	const ys = [...s.board.map((t) => t.y), ...spots.map((p) => p.y)];
	const minX = Math.min(...xs) - 0.5;
	const maxX = Math.max(...xs) + 1.5;
	const minY = Math.min(...ys) - 0.5;
	const maxY = Math.max(...ys) + 1.5;
	const rect = canvas.getBoundingClientRect();
	const dpr = window.devicePixelRatio || 1;
	canvas.width = Math.round(rect.width * dpr);
	canvas.height = Math.round(rect.height * dpr);
	const cell = Math.min(
		110 * dpr,
		canvas.width / (maxX - minX),
		canvas.height / (maxY - minY),
	);
	view = {
		cell,
		ox: (canvas.width - cell * (maxX - minX)) / 2 - minX * cell,
		oy: (canvas.height - cell * (maxY - minY)) / 2 - minY * cell,
	};
	// Where the board is drawn, so a browser test can click on cells.
	canvas.dataset.view = JSON.stringify(view);
}

const toScreen = (x: number, y: number): [number, number] => [
	view.ox + x * view.cell,
	view.oy + y * view.cell,
];

function render() {
	const s = game.state;
	layout();
	const { cell } = view;
	ctx.fillStyle =
		getComputedStyle(document.body).getPropertyValue("--board").trim() ||
		"#2b3a2e";
	ctx.fillRect(0, 0, canvas.width, canvas.height);
	for (const t of s.board)
		drawTile(ctx, t.code, ...toScreen(t.x, t.y), cell, t.r);
	const last =
		s.board.length > 1 ? (s.board[s.board.length - 1] as Placed) : null;
	if (last) {
		ctx.strokeStyle = "rgba(255,255,255,0.8)";
		ctx.lineWidth = 2;
		ctx.strokeRect(...toScreen(last.x, last.y), cell, cell);
	}
	for (const m of s.meeples)
		drawMeeple(ctx, ...toScreen(...meeplePoint(m, s.board)), cell, m.player);

	const code = s.hands[s.turn];
	if (!s.over && code) {
		const seen = new Set<string>();
		for (const p of placements(s)) {
			const k = `${p.x},${p.y}`;
			if (seen.has(k)) continue;
			seen.add(k);
			const [px, py] = toScreen(p.x, p.y);
			ctx.fillStyle = "rgba(255,255,255,0.18)";
			ctx.fillRect(px + 3, py + 3, cell - 6, cell - 6);
			ctx.strokeStyle = "rgba(255,255,255,0.5)";
			ctx.setLineDash([6, 4]);
			ctx.strokeRect(px + 3, py + 3, cell - 6, cell - 6);
			ctx.setLineDash([]);
		}
		if (pick) {
			drawTile(ctx, code, ...toScreen(pick.x, pick.y), cell, pick.r, 0.92);
			const placed = { ...pick, code };
			for (const ref of meepleSpots(s, pick)) {
				const [mx, my] = toScreen(...anchorPoint(placed, ref));
				drawMeeple(ctx, mx, my, cell, s.turn, ref !== chosen);
			}
		}
	}
	renderPanel();
}

function renderPanel() {
	const s = game.state;
	for (const p of [0, 1] as Player[]) {
		$(`score${p}`).textContent = String(s.scores[p]);
		$(`meeples${p}`).textContent = `${meeplesLeft(s, p)} meeples`;
		$(`card${p}`).classList.toggle("active", !s.over && s.turn === p);
		const hand = $<HTMLCanvasElement>(`hand${p}`);
		const g = hand.getContext("2d") as CanvasRenderingContext2D;
		g.clearRect(0, 0, hand.width, hand.height);
		const code = s.hands[p];
		if (code)
			drawTile(g, code, 0, 0, hand.width, s.turn === p && pick ? pick.r : 0);
	}
	$("left").textContent =
		`${s.deck.length} tiles to draw${s.discards.length ? `, ${s.discards.length} set aside` : ""}`;
	$("seed").textContent =
		game.seed === null ? "hand-made set" : `set #${game.seed}`;
	const w = winner(s);
	if (s.over && w !== null) {
		const tie = s.scores[0] === s.scores[1];
		status.textContent = `Game over: ${NAMES[w]} wins ${s.scores[w]} to ${s.scores[w === 0 ? 1 : 0]}${tie ? " (a tie goes against the starting player)" : ""}.`;
	} else if (!pick)
		status.textContent = `${NAMES[s.turn]} to play: pick a highlighted spot.`;
	else
		status.textContent = `${NAMES[s.turn]}: rotate, tap a circle to add a meeple, then place.`;
	$<HTMLButtonElement>("rotate").disabled = !pick;
	$<HTMLButtonElement>("place").disabled = !pick;
	$<HTMLButtonElement>("cancel").disabled = !pick;
}

function say(text: string) {
	message.textContent = text;
}

function rotations(x: number, y: number): number[] {
	return placements(game.state)
		.filter((p) => p.x === x && p.y === y)
		.map((p) => p.r);
}

canvas.addEventListener("click", (e: MouseEvent) => {
	const s = game.state;
	if (s.over) return;
	const rect = canvas.getBoundingClientRect();
	const dpr = canvas.width / rect.width;
	const sx = (e.clientX - rect.left) * dpr;
	const sy = (e.clientY - rect.top) * dpr;
	const bx = (sx - view.ox) / view.cell;
	const by = (sy - view.oy) / view.cell;
	const code = s.hands[s.turn];
	if (pick && code) {
		// The nearest meeple circle on the tried tile, if the click is on one.
		let best: { ref: FeatureRef; d: number } | null = null;
		for (const ref of meepleSpots(s, pick)) {
			const [ax, ay] = anchorPoint({ ...pick, code }, ref);
			const d = Math.hypot(ax - bx, ay - by);
			if (d < 0.12 && (!best || d < best.d)) best = { ref, d };
		}
		if (best) {
			chosen = chosen === best.ref ? null : best.ref;
			render();
			return;
		}
	}
	const x = Math.floor(bx);
	const y = Math.floor(by);
	const rs = rotations(x, y);
	if (!rs.length) return;
	if (pick && pick.x === x && pick.y === y) rotate();
	else {
		pick = { x, y, r: rs[0] as number };
		chosen = null;
		say("");
		render();
	}
});

function rotate() {
	if (!pick) return;
	const rs = rotations(pick.x, pick.y);
	const i = rs.indexOf(pick.r);
	pick = { ...pick, r: rs[(i + 1) % rs.length] as number };
	chosen = null;
	render();
}

function place() {
	if (!pick) return;
	const next = play(game, { ...pick, meeple: chosen });
	if (typeof next === "string") {
		say(next);
		return;
	}
	const before = game.state.scores;
	game = next;
	const gained = game.state.scores.map((v, i) => v - (before[i] as number));
	say(
		gained.some((g) => g > 0)
			? gained
					.map((g, i) => (g ? `${NAMES[i]} +${g}` : ""))
					.filter(Boolean)
					.join(", ")
			: "",
	);
	pick = null;
	chosen = null;
	render();
}

$("rotate").addEventListener("click", rotate);
$("place").addEventListener("click", place);
$("cancel").addEventListener("click", () => {
	pick = null;
	chosen = null;
	render();
});
$("new").addEventListener("click", () => fresh(newSeed(), 0));
$("rematch").addEventListener("click", () => {
	if (game.seed === null) return say("A hand-made set has no seed to replay.");
	fresh(game.seed, game.state.starter === 0 ? 1 : 0);
	say("Same tiles, seats swapped: the other player starts.");
});
$("save").addEventListener("click", () => {
	const blob = new Blob([save(game)], { type: "application/json" });
	const a = document.createElement("a");
	a.href = URL.createObjectURL(blob);
	a.download = `tile-game-${game.seed ?? "custom"}-${game.moves.length}.json`;
	a.click();
	setTimeout(() => URL.revokeObjectURL(a.href), 1000);
});
const file = $<HTMLInputElement>("file");
$("load").addEventListener("click", () => file.click());
file.addEventListener("change", async () => {
	const f = file.files?.[0];
	if (!f) return;
	try {
		game = load(await f.text());
		pick = null;
		chosen = null;
		say(`Loaded ${f.name}.`);
	} catch (e) {
		say(`Couldn't load ${f.name}: ${(e as Error).message}`);
	}
	file.value = "";
	render();
});
document.addEventListener("keydown", (e: KeyboardEvent) => {
	if (e.key === "r" || e.key === "R") rotate();
	else if (e.key === "Enter") place();
	else if (e.key === "Escape") {
		pick = null;
		chosen = null;
		render();
	}
});
window.addEventListener("resize", render);

render();
