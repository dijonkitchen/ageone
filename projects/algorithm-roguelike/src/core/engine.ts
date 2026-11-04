// The engine core: a run's state and how one input changes it. It knows nothing about any concept by
// name; everything a concept adds (floor generators, vision, schedulers, monster brains, loot, the pack,
// and actions) comes through its hooks. Same seed and inputs, same run.
import {
	carveRect,
	DIRS8,
	emptyFloor,
	type Floor,
	floorCells,
	index,
	type Point,
	passable,
	SHRINE,
	STAIRS,
	tileAt,
} from "./grid";
import { Rng } from "./rng";
import type {
	Concept,
	Ctx,
	Generated,
	Hooks,
	ItemKind,
	Monster,
	State,
} from "./types";

export const MONSTERS: Record<
	string,
	{
		glyph: string;
		name: string;
		hp: number;
		atk: number;
		speed: number;
		erratic?: boolean;
		from: number;
	}
> = {
	rat: { glyph: "r", name: "rat", hp: 3, atk: 1, speed: 100, from: 1 },
	bat: {
		glyph: "b",
		name: "bat",
		hp: 2,
		atk: 1,
		speed: 200,
		erratic: true,
		from: 2,
	},
	goblin: { glyph: "g", name: "goblin", hp: 5, atk: 2, speed: 100, from: 2 },
	zombie: { glyph: "z", name: "zombie", hp: 8, atk: 3, speed: 50, from: 3 },
};

export const ITEMS: Record<ItemKind, { glyph: string; about: string }> = {
	"healing potion": { glyph: "!", about: "Heals 8." },
	dart: { glyph: ")", about: "Thrown at a monster in sight." },
	"haste potion": { glyph: "!", about: "Doubles your speed for 10 turns." },
	"vigor amulet": { glyph: '"', about: "Raises your health by 5 for good." },
	page: { glyph: "?", about: "A codex page: learn it at a shrine." },
};

export const PLAYER_HP = 20;
export const TORCH = 3;
const W = 46;
const H = 19;

/** What the engine runs with: the concepts, and the player's code for functions they switched on. */
export interface Env {
	concepts: Concept[];
	code?: (name: string) => ((...args: unknown[]) => unknown) | null;
	codeFailed?: (name: string, error: string) => void;
}

const unlocked = (env: Env, s: State) =>
	env.concepts.filter((c) => s.unlocked.includes(c.id));

/** The unlocked hook of a kind with the highest priority. */
function best<
	K extends "generator" | "scheduler" | "brain" | "loot" | "inventory",
>(env: Env, s: State, key: K): NonNullable<Hooks[K]> | null {
	let out: NonNullable<Hooks[K]> | null = null;
	for (const c of unlocked(env, s)) {
		const h = c.hooks[key];
		if (h && (!out || h.priority > out.priority))
			out = h as NonNullable<Hooks[K]>;
	}
	return out;
}

export function context(env: Env, s: State): Ctx {
	const rng = new Rng(s.rng);
	return {
		rng,
		has: (id) => s.unlocked.includes(id),
		say: (m) => say(s, m),
		code(name, reference, valid) {
			const player = env.code?.(name);
			if (!player) return reference;
			return ((...args: never[]) => {
				try {
					const r = player(...args);
					if (r === undefined || (valid && !valid(r)))
						throw new Error("it returned something the game can't use");
					return r;
				} catch (e) {
					const why = e instanceof Error ? e.message : String(e);
					env.codeFailed?.(name, why);
					say(
						s,
						`Your ${name} failed (${why}); the reference runs it from here.`,
					);
					return reference(...args);
				}
			}) as typeof reference;
		},
	};
}

/** Run `fn` with a context whose random numbers are saved back into the state. */
function withCtx<T>(env: Env, s: State, fn: (ctx: Ctx) => T): T {
	const ctx = context(env, s);
	try {
		return fn(ctx);
	} finally {
		s.rng = ctx.rng.state;
	}
}

export function say(s: State, m: string) {
	s.log.push(m);
	if (s.log.length > 60) s.log.splice(0, s.log.length - 60);
}

// ---- Floors -------------------------------------------------------------------------------------

/** The floor before any concept is learned: one hand-made room with a shrine and stairs. */
export function singleRoom(): Generated {
	const floor = emptyFloor(W, H);
	const x0 = 17;
	const y0 = 8;
	carveRect(floor, x0, y0, 11, 3, 0);
	floor.tiles[index(floor, x0 + 1, y0 + 1)] = SHRINE;
	floor.tiles[index(floor, x0 + 9, y0 + 1)] = STAIRS;
	return { floor, start: [x0 + 3, y0 + 1] };
}

export function shrineAt(f: Floor): Point | null {
	const i = f.tiles.indexOf(SHRINE);
	return i < 0 ? null : [i % f.w, Math.floor(i / f.w)];
}

/** The shrine's safe area: its room, or two steps around it; monsters never enter it. */
export function isSafe(f: Floor, x: number, y: number): boolean {
	if (f.shrineRoom >= 0) return f.room[index(f, x, y)] === f.shrineRoom;
	const s = shrineAt(f);
	return !!s && Math.max(Math.abs(s[0] - x), Math.abs(s[1] - y)) <= 2;
}

/** The next concept to find: the first locked one, in tier order, whose prerequisites are learned. */
export function nextConcept(env: Env, s: State): Concept | null {
	const taken = new Set([
		...s.unlocked,
		...s.pages,
		...s.items.flatMap((i) => (i.concept ? [i.concept] : [])),
	]);
	const ready = env.concepts.filter(
		(c) => !taken.has(c.id) && c.requires.every((r) => s.unlocked.includes(r)),
	);
	return ready.sort((a, b) => a.tier - b.tier)[0] ?? null;
}

function enterFloor(env: Env, s: State) {
	withCtx(env, s, (ctx) => {
		const gen = best(env, s, "generator");
		const { floor, start } = gen ? gen.generate(ctx, s.depth) : singleRoom();
		s.floor = floor;
		[s.player.x, s.player.y] = start;
		s.monsters = [];
		s.items = [];
		s.sched = null;
		s.undo = { used: false, stack: [] };
		const far = (i: number) => {
			const x = i % floor.w;
			const y = Math.floor(i / floor.w);
			return (
				!isSafe(floor, x, y) &&
				Math.max(Math.abs(x - start[0]), Math.abs(y - start[1])) > 4
			);
		};
		const free = ctx.rng.shuffle(floorCells(floor, far));
		const take = () => free.pop();
		const kinds = Object.entries(MONSTERS).filter(([, m]) => m.from <= s.depth);
		const count = gen ? Math.min(2 + s.depth, 12) : 1;
		for (let i = 0; i < count; i++) {
			const at = take();
			if (!at) break;
			const [kind, m] = ctx.rng.pick(kinds);
			s.monsters.push({ id: s.nextId++, kind, x: at[0], y: at[1], hp: m.hp });
		}
		const loot = best(env, s, "loot");
		const drops = gen ? 2 + ctx.rng.int(2) : 1;
		for (let i = 0; i < drops; i++) {
			const at = take();
			if (at)
				s.items.push({
					x: at[0],
					y: at[1],
					kind: loot ? loot.roll(ctx, s.depth) : baseLoot(ctx),
				});
		}
		const page = nextConcept(env, s);
		const at = gen ? take() : ([start[0] + 1, start[1]] as Point);
		if (page && at)
			s.items.push({ x: at[0], y: at[1], kind: "page", concept: page.id });
		say(
			s,
			gen
				? `You reach depth ${s.depth}.`
				: `Depth ${s.depth}: a single room. A codex page lies here, and a shrine (_) to study it.`,
		);
	});
	updateVision(env, s);
}

const baseLoot = (ctx: Ctx): ItemKind =>
	ctx.rng.chance(0.7) ? "healing potion" : "dart";

export function newRun(env: Env, seed: number, learned: string[] = []): State {
	const s: State = {
		version: 1,
		seed,
		rng: seed,
		depth: 1,
		turn: 0,
		time: 0,
		seq: 0,
		nextId: 1,
		unlocked: env.concepts
			.filter((c) => learned.includes(c.id))
			.map((c) => c.id),
		pages: [],
		floor: emptyFloor(1, 1),
		player: {
			x: 0,
			y: 0,
			hp: PLAYER_HP,
			maxHp: PLAYER_HP,
			haste: 0,
			hasteBank: 0,
		},
		monsters: [],
		items: [],
		inventory: [],
		sched: null,
		undo: { used: false, stack: [] },
		visible: [],
		log: [],
		over: false,
	};
	enterFloor(env, s);
	return s;
}

// ---- Vision ---------------------------------------------------------------------------------------

export const remembers = (env: Env, s: State) =>
	unlocked(env, s).some((c) => c.hooks.memory);

export function updateVision(env: Env, s: State) {
	const f = s.floor;
	const seen = new Set<number>();
	// Without any concept you see by torchlight: three cells around you.
	for (let dy = -TORCH; dy <= TORCH; dy++)
		for (let dx = -TORCH; dx <= TORCH; dx++) {
			const x = s.player.x + dx;
			const y = s.player.y + dy;
			if (x >= 0 && y >= 0 && x < f.w && y < f.h) seen.add(index(f, x, y));
		}
	withCtx(env, s, (ctx) => {
		for (const c of unlocked(env, s))
			if (c.hooks.vision) for (const i of c.hooks.vision(ctx, s)) seen.add(i);
	});
	s.visible = [...seen].sort((a, b) => a - b);
	for (const i of s.visible) f.seen[i] = 1;
}

// ---- Acting -------------------------------------------------------------------------------------

export const monsterAt = (s: State, x: number, y: number) =>
	s.monsters.find((m) => m.x === x && m.y === y && m.hp > 0);

/** Can a monster stand here? */
export const open = (s: State, x: number, y: number) =>
	passable(tileAt(s.floor, x, y)) &&
	!isSafe(s.floor, x, y) &&
	!monsterAt(s, x, y) &&
	!(s.player.x === x && s.player.y === y);

/** The step a monster takes without a better brain: toward the player when near, else a random one. */
function baseStep(ctx: Ctx, s: State, m: Monster): Point | null {
	const { x, y } = s.player;
	const dist = Math.max(Math.abs(m.x - x), Math.abs(m.y - y));
	if (dist <= 1) return [x, y];
	const options = DIRS8.map(([dx, dy]) => [m.x + dx, m.y + dy] as Point).filter(
		([nx, ny]) => open(s, nx, ny),
	);
	if (!options.length) return null;
	if (
		MONSTERS[m.kind]?.erratic
			? ctx.rng.chance(0.5)
			: Math.abs(m.x - x) + Math.abs(m.y - y) > 7
	)
		return ctx.rng.chance(0.5) ? ctx.rng.pick(options) : null;
	const d = ([px, py]: Point) =>
		Math.max(Math.abs(px - x), Math.abs(py - y)) * 10 +
		Math.abs(px - x) +
		Math.abs(py - y);
	return options.reduce((a, b) => (d(b) < d(a) ? b : a));
}

function hurtPlayer(s: State, m: Monster, rng: Rng) {
	const kind = MONSTERS[m.kind];
	if (!kind) return;
	const dmg = rng.range(1, kind.atk);
	s.player.hp -= dmg;
	say(s, `The ${kind.name} hits you for ${dmg}.`);
	if (s.player.hp <= 0 && !s.over) {
		s.over = true;
		say(
			s,
			`You die on depth ${s.depth}, killed by a ${kind.name}. What you learned stays learned.`,
		);
	}
}

export function hurtMonster(s: State, m: Monster, dmg: number, how: string) {
	const kind = MONSTERS[m.kind];
	m.hp -= dmg;
	if (m.hp <= 0) {
		say(s, `You ${how} the ${kind?.name ?? m.kind} for ${dmg}; it dies.`);
		s.monsters = s.monsters.filter((x) => x !== m);
	} else say(s, `You ${how} the ${kind?.name ?? m.kind} for ${dmg}.`);
}

/** One monster's turn. */
function act(env: Env, s: State, ctx: Ctx, id: number) {
	const m = s.monsters.find((x) => x.id === id);
	if (!m || m.hp <= 0 || s.over) return;
	const brain = best(env, s, "brain");
	const to = brain ? brain.step(ctx, s, m) : baseStep(ctx, s, m);
	if (!to) return;
	const [x, y] = to;
	if (Math.max(Math.abs(x - m.x), Math.abs(y - m.y)) > 1) return;
	if (x === s.player.x && y === s.player.y) {
		if (!isSafe(s.floor, x, y)) hurtPlayer(s, m, ctx.rng);
	} else if (open(s, x, y)) [m.x, m.y] = [x, y];
}

/** Everyone else's turns after the player acted. */
function others(env: Env, s: State, ctx: Ctx) {
	const cost = s.player.haste > 0 ? 50 : 100;
	if (s.player.haste > 0) s.player.haste--;
	const sched = best(env, s, "scheduler");
	const run = (id: number) => act(env, s, ctx, id);
	if (sched) {
		sched.afterPlayer(ctx, s, run, cost);
		return;
	}
	// Without a scheduler everyone acts once a round; haste gives the player every other round free.
	if (cost < 100) {
		s.player.hasteBank ^= 1;
		if (s.player.hasteBank) return;
	}
	for (const m of [...s.monsters]) run(m.id);
}

export function inventoryPolicy(env: Env, s: State) {
	return best(env, s, "inventory") ?? { priority: 0, stacks: false, limit: 4 };
}

function pickUp(env: Env, s: State) {
	const { x, y } = s.player;
	for (const item of s.items.filter((i) => i.x === x && i.y === y)) {
		if (item.kind === "page") {
			s.pages.push(item.concept ?? "");
			const c = env.concepts.find((k) => k.id === item.concept);
			say(s, `You find a codex page: ${c?.name}. Study it at a shrine (_).`);
		} else {
			const policy = inventoryPolicy(env, s);
			const stack = policy.stacks
				? s.inventory.find((st) => st.kind === item.kind)
				: undefined;
			if (stack) stack.count++;
			else if (s.inventory.length < policy.limit)
				s.inventory.push({ kind: item.kind, count: 1 });
			else {
				say(s, `Your pack is full; the ${item.kind} stays here.`);
				continue;
			}
			say(s, `You pick up a ${item.kind}.`);
		}
		s.items = s.items.filter((i) => i !== item);
	}
}

export function removeOne(s: State, slot: number) {
	const st = s.inventory[slot];
	if (!st) return;
	st.count--;
	if (st.count <= 0) s.inventory.splice(slot, 1);
}

/** Use the item in a slot (0-based); returns whether it took a turn. */
export function useItem(s: State, slot: number): boolean {
	const st = s.inventory[slot];
	if (!st) {
		say(s, "Nothing in that slot.");
		return false;
	}
	const p = s.player;
	switch (st.kind) {
		case "healing potion":
			p.hp = Math.min(p.maxHp, p.hp + 8);
			say(s, "You drink a healing potion.");
			break;
		case "haste potion":
			p.haste = 10;
			say(s, "You drink a haste potion; the world slows down.");
			break;
		case "vigor amulet":
			p.maxHp += 5;
			p.hp += 5;
			say(s, "You put on the vigor amulet: +5 health.");
			break;
		default:
			say(s, "Darts are thrown (t) once you learn Bresenham lines.");
			return false;
	}
	removeOne(s, slot);
	return true;
}

const snapshot = (s: State) => JSON.stringify({ ...s, undo: undefined });

/** Put back the state saved before the last turn (the stack concept's undo uses it). */
export function restore(s: State, saved: string) {
	const old = JSON.parse(saved) as State;
	Object.assign(s, { ...old, undo: s.undo });
}

/** Apply one input. Inputs: `move:dx,dy`, `wait`, `descend`, `use:<slot>`, `learn:<concept>`, `act:<name>`. */
export function step(env: Env, s: State, input: string) {
	if (s.over) return;
	const [verb, arg = ""] = input.split(/:(.*)/s) as [string, string?];
	if (verb === "learn") {
		learn(env, s, arg);
		return;
	}
	const before = snapshot(s);
	let took = false;
	if (verb === "move") {
		const [dx, dy] = arg.split(",").map(Number) as [number, number];
		const x = s.player.x + dx;
		const y = s.player.y + dy;
		const m = monsterAt(s, x, y);
		if (Math.max(Math.abs(dx), Math.abs(dy)) !== 1) took = false;
		else if (m) {
			withCtx(env, s, (ctx) =>
				hurtMonster(s, m, ctx.rng.range(1, 3) + Math.floor(s.depth / 3), "hit"),
			);
			took = true;
		} else if (passable(tileAt(s.floor, x, y))) {
			[s.player.x, s.player.y] = [x, y];
			pickUp(env, s);
			if (tileAt(s.floor, x, y) === SHRINE)
				say(
					s,
					s.pages.length
						? "A shrine. Study your codex pages here."
						: "A shrine. Bring codex pages here to study them.",
				);
			if (tileAt(s.floor, x, y) === STAIRS) say(s, "Stairs down (press >).");
			took = true;
		}
	} else if (verb === "wait") took = true;
	else if (verb === "descend") {
		if (tileAt(s.floor, s.player.x, s.player.y) !== STAIRS)
			say(s, "There are no stairs here.");
		else {
			s.depth++;
			s.turn++;
			enterFloor(env, s);
			return;
		}
	} else if (verb === "use") took = useItem(s, Number(arg) - 1);
	else if (verb === "act") {
		const a = unlocked(env, s)
			.map((c) => c.hooks.actions?.[arg.split(":")[0] ?? ""])
			.find(Boolean);
		if (!a) say(s, "You don't know how to do that yet.");
		else took = withCtx(env, s, (ctx) => a.run(ctx, s, arg.split(":")[1]));
	}
	if (!took) {
		updateVision(env, s);
		return;
	}
	s.undo.stack.push(before);
	if (s.undo.stack.length > 20) s.undo.stack.shift();
	s.turn++;
	withCtx(env, s, (ctx) => others(env, s, ctx));
	updateVision(env, s);
}

/** Learn a concept from a carried page while standing on a shrine. */
export function learn(env: Env, s: State, id: string): boolean {
	const c = env.concepts.find((k) => k.id === id);
	const why = !c
		? "There is no such concept."
		: s.unlocked.includes(id)
			? `You already know ${c.name}.`
			: !s.pages.includes(id)
				? `You need ${c.name}'s codex page.`
				: tileAt(s.floor, s.player.x, s.player.y) !== SHRINE
					? "Study at a shrine (_)."
					: c.requires.find((r) => !s.unlocked.includes(r))
						? `Learn ${c.requires.filter((r) => !s.unlocked.includes(r)).join(", ")} first.`
						: null;
	if (why || !c) {
		say(s, why ?? "");
		return false;
	}
	s.unlocked.push(id);
	s.pages = s.pages.filter((p) => p !== id);
	say(s, `You learned ${c.name}: ${c.unlocks}`);
	updateVision(env, s);
	return true;
}

/** Replay a run from its seed, what was learned before it, and its inputs. */
export function replay(
	env: Env,
	seed: number,
	learned: string[],
	inputs: string[],
): State {
	const s = newRun(env, seed, learned);
	for (const i of inputs) step(env, s, i);
	return s;
}

/** A stable fingerprint of a run's state (the undo history is left out). */
export const fingerprint = (s: State) => snapshot(s);
