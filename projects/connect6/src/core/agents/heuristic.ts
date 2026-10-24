/**
 * A small but non-trivial heuristic agent. Priorities, in order:
 *   1. play a stone that wins immediately (AC-PLAYERS-3);
 *   2. otherwise block an opponent stone that would win immediately
 *      (AC-PLAYERS-4);
 *   3. otherwise take the highest-scoring cells by a line-potential
 *      heuristic (own offence + weighted defence + slight centre bias).
 *
 * This is intentionally simple; an MCTS engine or an LLM agent can replace
 * it behind the same `Agent` interface (spec §5).
 */

import { cellAt, emptyPositions, inBounds, isEmpty, place } from "../board.js";
import { requiredStones } from "../game.js";
import { findWinningLine } from "../rules.js";
import type { Cell, GameState, Move, Player, Position } from "../types.js";
import { otherPlayer, positionKey, WIN_LENGTH } from "../types.js";
import type { Agent } from "./agent.js";

const AXES: ReadonlyArray<readonly [number, number]> = [
	[0, 1],
	[1, 0],
	[1, 1],
	[1, -1],
];

const CANDIDATE_RADIUS = 2;

type Grid = ReadonlyArray<ReadonlyArray<Cell>>;

/** Empty cells within CANDIDATE_RADIUS of any stone; centre if board empty. */
const candidateCells = (state: GameState): Position[] => {
	const { board, size } = state;
	const seen = new Set<string>();
	const out: Position[] = [];
	let anyStone = false;
	for (let r = 0; r < size; r += 1) {
		for (let c = 0; c < size; c += 1) {
			if (cellAt(board, { row: r, col: c }) === null) continue;
			anyStone = true;
			for (let dr = -CANDIDATE_RADIUS; dr <= CANDIDATE_RADIUS; dr += 1) {
				for (let dc = -CANDIDATE_RADIUS; dc <= CANDIDATE_RADIUS; dc += 1) {
					const pos = { row: r + dr, col: c + dc };
					if (!inBounds(size, pos) || !isEmpty(board, pos)) continue;
					const key = positionKey(pos);
					if (seen.has(key)) continue;
					seen.add(key);
					out.push(pos);
				}
			}
		}
	}
	if (!anyStone) {
		const mid = Math.floor(size / 2);
		return [{ row: mid, col: mid }];
	}
	return out;
};

/** Cells where a single `player` stone completes a winning run. */
const winningCellsFor = (
	board: Grid,
	size: number,
	player: Player,
	candidates: readonly Position[],
): Position[] => {
	const wins: Position[] = [];
	for (const pos of candidates) {
		const test = place(board, [pos], player);
		if (findWinningLine(test, size, player, [pos])) wins.push(pos);
	}
	return wins;
};

const countDir = (
	board: Grid,
	size: number,
	pos: Position,
	dr: number,
	dc: number,
	player: Player,
): { count: number; open: boolean } => {
	let count = 0;
	let r = pos.row + dr;
	let c = pos.col + dc;
	while (
		inBounds(size, { row: r, col: c }) &&
		cellAt(board, { row: r, col: c }) === player
	) {
		count += 1;
		r += dr;
		c += dc;
	}
	const open =
		inBounds(size, { row: r, col: c }) &&
		cellAt(board, { row: r, col: c }) === null;
	return { count, open };
};

const runWeight = (len: number, openEnds: number): number => {
	if (len >= WIN_LENGTH) return 1_000_000;
	if (openEnds === 0) return len; // dead run: occupies space but cannot extend
	return len * len * (openEnds + 1);
};

/** Value of placing `player` at `pos`, summed over the four axes. */
const lineValueFor = (
	board: Grid,
	size: number,
	pos: Position,
	player: Player,
): number => {
	let total = 0;
	for (const [dr, dc] of AXES) {
		const fwd = countDir(board, size, pos, dr, dc, player);
		const back = countDir(board, size, pos, -dr, -dc, player);
		const len = fwd.count + back.count + 1;
		const openEnds = (fwd.open ? 1 : 0) + (back.open ? 1 : 0);
		total += runWeight(len, openEnds);
	}
	return total;
};

const scoreCell = (
	board: Grid,
	size: number,
	pos: Position,
	player: Player,
): number => {
	const offence = lineValueFor(board, size, pos, player);
	const defence = lineValueFor(board, size, pos, otherPlayer(player));
	const mid = (size - 1) / 2;
	const centreBias =
		-(Math.abs(pos.row - mid) + Math.abs(pos.col - mid)) * 0.01;
	return offence + 0.9 * defence + centreBias;
};

export class HeuristicAgent implements Agent {
	readonly name = "heuristic";

	async chooseMove(state: GameState): Promise<Move> {
		const { board, size } = state;
		const player = state.toMove;
		const opponent = otherPlayer(player);
		const required = requiredStones(state);
		const candidates = candidateCells(state);

		const picks: Position[] = [];
		const used = new Set<string>();
		const take = (pos: Position): void => {
			const key = positionKey(pos);
			if (!used.has(key)) {
				used.add(key);
				picks.push(pos);
			}
		};

		// 1. Win now if we can.
		const ownWins = winningCellsFor(board, size, player, candidates);
		const firstWin = ownWins[0];
		if (firstWin) take(firstWin);

		// 2. Otherwise block the opponent's immediate winning cells.
		if (picks.length === 0) {
			for (const threat of winningCellsFor(board, size, opponent, candidates)) {
				if (picks.length >= required) break;
				take(threat);
			}
		}

		// 3. Fill the rest with the best-scoring candidates.
		if (picks.length < required) {
			const ranked = candidates
				.filter((p) => !used.has(positionKey(p)))
				.map((p) => ({ p, score: scoreCell(board, size, p, player) }))
				.sort((a, b) => b.score - a.score);
			for (const { p } of ranked) {
				if (picks.length >= required) break;
				take(p);
			}
		}

		// 4. Safety net for nearly full boards.
		if (picks.length < required) {
			for (const p of emptyPositions(board)) {
				if (picks.length >= required) break;
				take(p);
			}
		}

		return { positions: picks };
	}
}
