/**
 * Plays one game between two agents to the end. A player that throws
 * ForfeitError, or returns an illegal move, loses; any other error propagates.
 */

import {
	type Agent,
	applyMove,
	createGame,
	ForfeitError,
	type GameState,
	IllegalMoveError,
	isGameOver,
	otherPlayer,
	type Player,
} from "./core/index.js";

export interface MatchResult {
	readonly state: GameState;
	readonly winner: Player | "draw";
	readonly reason: "six" | "draw" | "forfeit";
	/** Why the loser forfeited, when it did. */
	readonly detail?: string;
}

export const playMatch = async (
	black: Agent,
	white: Agent,
	size?: number,
	onMove?: (state: GameState) => void,
): Promise<MatchResult> => {
	let state = createGame(size);
	while (!isGameOver(state)) {
		const agent = state.toMove === "black" ? black : white;
		try {
			state = applyMove(state, await agent.chooseMove(state));
		} catch (error) {
			if (error instanceof ForfeitError || error instanceof IllegalMoveError) {
				return {
					state,
					winner: otherPlayer(state.toMove),
					reason: "forfeit",
					detail: error.message,
				};
			}
			throw error;
		}
		onMove?.(state);
	}
	if (state.status === "draw") return { state, winner: "draw", reason: "draw" };
	return {
		state,
		winner: state.status === "black_won" ? "black" : "white",
		reason: "six",
	};
};
