/**
 * UI controller. Owns the pending selection and turn loop, and drives a
 * `GameClient`. It depends only on the core's interfaces, so pointing it at a
 * networked backend later means swapping `LocalGameClient` for a remote one —
 * nothing here changes (REQ-CLIENT, NFR-3).
 */

import {
	type Agent,
	type Chat,
	cellAt,
	createGame,
	ForfeitError,
	type GameClient,
	type GameState,
	HeuristicAgent,
	isGameOver,
	LlmAgent,
	LocalGameClient,
	MctsAgent,
	type Player,
	type Position,
	positionKey,
	RandomAgent,
	requiredStones,
	validateMove,
} from "../core/index.js";
import { renderBoard } from "./render.js";

type PlayerKind = "human" | "heuristic" | "mcts" | "random" | "llm";

const mustGet = <T extends HTMLElement>(id: string): T => {
	const el = document.getElementById(id);
	if (!el) throw new Error(`missing element #${id}`);
	return el as T;
};

const boardEl = mustGet<HTMLElement>("board");
const statusEl = mustGet<HTMLOutputElement>("status");
const newGameBtn = mustGet<HTMLButtonElement>("new-game");
const blackSelect = mustGet<HTMLSelectElement>("black-player");
const whiteSelect = mustGet<HTMLSelectElement>("white-player");

const client: GameClient = new LocalGameClient();
let state: GameState = createGame();
let pending: Position[] = [];
let busy = false; // blocks input while an async move (human submit or AI) runs
let forfeit: { player: Player; reason: string } | null = null;

const agents: Record<Player, Agent | null> = { black: null, white: null };

/** The LLM player's model calls go through the local server (src/cli/server.ts). */
const serverChat: Chat = async (messages) => {
	const response = await fetch("/api/chat", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ role: "cheap", messages }),
	});
	const data = await response.json();
	if (!response.ok) throw new Error(data.error ?? `HTTP ${response.status}`);
	return data;
};

const makeAgent = (kind: PlayerKind): Agent | null => {
	if (kind === "heuristic") return new HeuristicAgent();
	if (kind === "mcts") return new MctsAgent({ rng: Math.random });
	if (kind === "random") return new RandomAgent();
	if (kind === "llm") return new LlmAgent(serverChat);
	return null;
};

const isOver = (): boolean => forfeit !== null || isGameOver(state);

const delay = (ms: number): Promise<void> =>
	new Promise((resolve) => setTimeout(resolve, ms));

const colourName = (p: Player): string => (p === "black" ? "Black" : "White");

const statusText = (): string => {
	if (forfeit) {
		const winner = colourName(forfeit.player === "black" ? "white" : "black");
		return `${colourName(forfeit.player)} forfeits (${forfeit.reason}). ${winner} wins!`;
	}
	switch (state.status) {
		case "black_won":
			return "Black wins!";
		case "white_won":
			return "White wins!";
		case "draw":
			return "Draw — the board is full.";
		case "in_progress": {
			const who = colourName(state.toMove);
			if (agents[state.toMove]) return `${who} (AI) is thinking…`;
			const need = requiredStones(state) - pending.length;
			return `${who} to move — place ${need} stone${need === 1 ? "" : "s"}.`;
		}
	}
};

const render = (): void => {
	renderBoard(boardEl, state, pending, onCellClick);
	statusEl.textContent = statusText();
	statusEl.classList.toggle("over", isOver());
	boardEl.classList.toggle("busy", busy);
};

const onCellClick = (pos: Position): void => {
	if (busy || isOver()) return;
	if (agents[state.toMove]) return; // not a human's turn

	const key = positionKey(pos);
	const existing = pending.findIndex((q) => positionKey(q) === key);
	if (existing >= 0) {
		pending.splice(existing, 1); // toggle off a pending stone
		render();
		return;
	}
	if (cellAt(state.board, pos) !== null) return;

	pending.push(pos);
	if (pending.length === requiredStones(state)) {
		void submitPending();
	} else {
		render();
	}
};

const submitPending = async (): Promise<void> => {
	const move = { positions: pending.slice() };
	if (!validateMove(state, move).ok) {
		pending = [];
		render();
		return;
	}
	busy = true;
	render();
	try {
		state = await client.applyMove(move);
		pending = [];
	} catch (error) {
		statusEl.textContent = (error as Error).message;
		pending = [];
	} finally {
		busy = false;
	}
	render();
	await runAiTurns();
};

// Bumped by each new game, so a loop still running for an old game stops.
let generation = 0;

const runAiTurns = async (): Promise<void> => {
	const game = generation;
	while (!isOver()) {
		const agent = agents[state.toMove];
		if (!agent) break;
		busy = true;
		render();
		await delay(250); // brief pause so moves are visible
		if (game !== generation) return;
		try {
			const move = await agent.chooseMove(state);
			if (game !== generation) return;
			state = await client.applyMove(move);
		} catch (error) {
			if (game !== generation) return;
			if (error instanceof ForfeitError) {
				forfeit = { player: state.toMove, reason: error.reason };
				busy = false;
				render();
				return;
			}
			statusEl.textContent = `AI error: ${(error as Error).message}`;
			busy = false;
			render();
			return;
		}
		busy = false;
		render();
	}
};

const newGame = async (): Promise<void> => {
	generation += 1;
	agents.black = makeAgent(blackSelect.value as PlayerKind);
	agents.white = makeAgent(whiteSelect.value as PlayerKind);
	state = await client.reset();
	pending = [];
	busy = false;
	forfeit = null;
	render();
	await runAiTurns();
};

newGameBtn.addEventListener("click", () => void newGame());
blackSelect.addEventListener("change", () => void newGame());
whiteSelect.addEventListener("change", () => void newGame());

void newGame();
