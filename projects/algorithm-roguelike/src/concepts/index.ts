// Every concept in the game, in the codex's order. Adding a concept is adding its folder and a line here.
import type { Concept } from "../core/types";
import { concept as alias } from "./alias";
import { concept as bfs } from "./bfs";
import { concept as bresenham } from "./bresenham";
import { concept as dijkstra } from "./dijkstra";
import { concept as grid } from "./grid";
import { concept as hashmap } from "./hashmap";
import { concept as heap } from "./heap";
import { concept as prng } from "./prng";
import { concept as randomwalk } from "./randomwalk";
import { concept as shadowcasting } from "./shadowcasting";
import { concept as stack } from "./stack";

export const CONCEPTS: Concept[] = [
	grid,
	stack,
	bfs,
	hashmap,
	prng,
	randomwalk,
	bresenham,
	shadowcasting,
	heap,
	dijkstra,
	alias,
];
