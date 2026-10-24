import { describe, expect, it } from "bun:test";
import {
	applyMove,
	type ChatMessage,
	type ChatReply,
	createGame,
	ForfeitError,
	HeuristicAgent,
	LlmAgent,
	parseMove,
	renderBoard,
	turnPrompt,
} from "../src/core/index.js";
import { playMatch } from "../src/match.js";

/** A model stub that answers from a list and records what it was sent. */
const scripted = (replies: string[]) => {
	const calls: ChatMessage[][] = [];
	const chat = async (messages: readonly ChatMessage[]): Promise<ChatReply> => {
		calls.push([...messages]);
		return { content: replies.shift() ?? "pass", tokens: 100, cost: 0.0002 };
	};
	return { chat, calls };
};

describe("LLM prompts and replies", () => {
	it("renders the board with column letters and row numbers", () => {
		const state = applyMove(createGame(7), {
			positions: [{ row: 0, col: 2 }],
		});
		const text = renderBoard(state);
		expect(text.split("\n")[0]).toBe("    A B C D E F G");
		expect(text.split("\n")[1]).toBe(" 1  . . X . . . .");
		expect(turnPrompt(state)).toContain("Your opponent just played C1.");
	});

	it("parses the points after MOVE:, ignoring earlier ones", () => {
		expect(parseMove("A1 looks weak.\nMOVE: J10 k11", 19)).toEqual([
			{ row: 9, col: 9 },
			{ row: 10, col: 10 },
		]);
		expect(parseMove("MOVE: Z99", 19)).toEqual([]);
	});
});

describe("LlmAgent (REQ-PLAYERS)", () => {
	it("AC-PLAYERS-7: plays a legal reply and counts its usage", async () => {
		const { chat } = scripted(["MOVE: J10"]);
		const agent = new LlmAgent(chat);
		const move = await agent.chooseMove(createGame());
		expect(move.positions).toEqual([{ row: 9, col: 9 }]);
		expect(agent.usage).toEqual({ tokens: 100, cost: 0.0002 });
	});

	it("AC-PLAYERS-7: shows an illegal reply back with the reason", async () => {
		const { chat, calls } = scripted(["MOVE: J10 K11", "MOVE: K10"]);
		const agent = new LlmAgent(chat);
		const move = await agent.chooseMove(createGame());
		expect(move.positions).toEqual([{ row: 9, col: 10 }]);
		expect(calls[1]?.at(-1)?.content).toContain("expected 1 point(s), found 2");
		expect(agent.invalidReplies).toBe(1);
	});

	it("AC-PLAYERS-7: forfeits after the bounded number of bad replies", async () => {
		const { chat, calls } = scripted(["no idea", "still no", "nope", "J10"]);
		const agent = new LlmAgent(chat, { maxAttempts: 3 });
		await expect(agent.chooseMove(createGame())).rejects.toBeInstanceOf(
			ForfeitError,
		);
		expect(calls).toHaveLength(3);
	});

	it("AC-PLAYERS-7: a failing model call forfeits instead of crashing", async () => {
		const agent = new LlmAgent(async () => {
			throw new Error("503");
		});
		await expect(agent.chooseMove(createGame())).rejects.toBeInstanceOf(
			ForfeitError,
		);
	});

	it("AC-PLAYERS-8: a forfeit ends the game for the opponent", async () => {
		const { chat } = scripted([]);
		const result = await playMatch(new HeuristicAgent(), new LlmAgent(chat));
		expect(result.winner).toBe("black");
		expect(result.reason).toBe("forfeit");
		expect(result.state.moveCount).toBe(1);
	});

	it("AC-PLAYERS-8: an illegal move from any player loses", async () => {
		const cheat = {
			name: "cheat",
			chooseMove: async () => ({ positions: [{ row: 0, col: 0 }] }),
		};
		const result = await playMatch(new HeuristicAgent(), cheat);
		expect(result).toMatchObject({ winner: "black", reason: "forfeit" });
	});
});
