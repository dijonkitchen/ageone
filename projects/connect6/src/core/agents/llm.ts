/**
 * A player that asks a language model for each turn. The model call itself is
 * injected as a `Chat` function, so this file stays free of network code: the
 * tournament passes an OpenRouter client and the browser passes one that goes
 * through the local server, which picks the model by role.
 *
 * An illegal or unparseable reply is shown back to the model with the reason,
 * up to `maxAttempts` replies in all; then the player forfeits.
 */

import { requiredStones } from "../game.js";
import { validateMove } from "../rules.js";
import type { GameState, Move, Position } from "../types.js";
import { WIN_LENGTH } from "../types.js";
import { type Agent, ForfeitError } from "./agent.js";

export interface ChatMessage {
	readonly role: "system" | "user" | "assistant";
	readonly content: string;
}

export interface ChatReply {
	readonly content: string;
	readonly tokens: number;
	/** USD, as reported by the provider; 0 when unknown. */
	readonly cost: number;
}

export type Chat = (messages: readonly ChatMessage[]) => Promise<ChatReply>;

const LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

/** Column letter and 1-based row, e.g. {row: 9, col: 9} is "J10". */
export const coordinate = (pos: Position): string =>
	`${LETTERS[pos.col] ?? "?"}${pos.row + 1}`;

export const renderBoard = (state: GameState): string => {
	const header = `    ${LETTERS.slice(0, state.size).split("").join(" ")}`;
	const rows = state.board.map(
		(row, r) =>
			`${String(r + 1).padStart(2)}  ${row
				.map((cell) => (cell === "black" ? "X" : cell === "white" ? "O" : "."))
				.join(" ")}`,
	);
	return [header, ...rows].join("\n");
};

export const SYSTEM_PROMPT = [
	`You are playing Connect6 on a square board. Players alternate turns; Black (X) opens with one stone, and every turn after places two stones on empty points.`,
	`The first player with ${WIN_LENGTH} or more stones in a row (horizontally, vertically, or diagonally) wins.`,
	"Points are named by column letter and row number, like J10.",
	"Think briefly if you like, then end your reply with one line: MOVE: followed by your points, for example MOVE: J10 K11.",
].join(" ");

export const turnPrompt = (state: GameState): string => {
	const me = state.toMove === "black" ? "Black (X)" : "White (O)";
	const need = requiredStones(state);
	const last = state.history.at(-1);
	return [
		renderBoard(state),
		"",
		last
			? `Your opponent just played ${last.positions.map(coordinate).join(" ")}.`
			: "The board is empty.",
		`You are ${me}. Place ${need} stone${need === 1 ? "" : "s"}.`,
	].join("\n");
};

/** Reads the points after the last "MOVE:", or anywhere in the reply. */
export const parseMove = (text: string, size: number): Position[] => {
	const marker = text.toUpperCase().lastIndexOf("MOVE:");
	const tail = marker >= 0 ? text.slice(marker + 5) : text;
	const out: Position[] = [];
	for (const match of tail.toUpperCase().matchAll(/\b([A-Z])\s?(\d{1,2})\b/g)) {
		const col = LETTERS.indexOf(match[1] ?? "");
		const row = Number(match[2]) - 1;
		if (col >= 0 && col < size && row >= 0 && row < size) {
			out.push({ row, col });
		}
	}
	return out;
};

export interface LlmAgentOptions {
	/** Replies allowed per turn before forfeiting. */
	readonly maxAttempts?: number;
	readonly name?: string;
}

export class LlmAgent implements Agent {
	readonly name: string;
	readonly usage = { tokens: 0, cost: 0 };
	/** Replies that were illegal or unparseable, across the game. */
	invalidReplies = 0;
	private readonly maxAttempts: number;

	constructor(
		private readonly chat: Chat,
		options: LlmAgentOptions = {},
	) {
		this.name = options.name ?? "llm";
		this.maxAttempts = options.maxAttempts ?? 3;
	}

	async chooseMove(state: GameState): Promise<Move> {
		const messages: ChatMessage[] = [
			{ role: "system", content: SYSTEM_PROMPT },
			{ role: "user", content: turnPrompt(state) },
		];
		let reason = "no reply";
		for (let attempt = 0; attempt < this.maxAttempts; attempt += 1) {
			let reply: ChatReply;
			try {
				reply = await this.chat(messages);
			} catch (error) {
				reason = `model call failed: ${(error as Error).message}`;
				continue;
			}
			this.usage.tokens += reply.tokens;
			this.usage.cost += reply.cost;
			const positions = parseMove(reply.content, state.size);
			const need = requiredStones(state);
			const move: Move = { positions: positions.slice(0, need) };
			const legality =
				positions.length === need
					? validateMove(state, move)
					: {
							ok: false as const,
							reason: `expected ${need} point(s), found ${positions.length}`,
						};
			if (legality.ok) return move;
			reason = legality.reason;
			this.invalidReplies += 1;
			messages.push(
				{ role: "assistant", content: reply.content },
				{
					role: "user",
					content: `That move is not legal: ${reason}. Reply again, ending with MOVE: and ${need} empty point(s).`,
				},
			);
		}
		throw new ForfeitError(`${this.name} gave no legal move (${reason})`);
	}
}
