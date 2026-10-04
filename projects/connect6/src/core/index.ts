/** Public API of the pure Connect6 core. UI, AI, and any backend import
 * from here. */

export * from "./agents/index.js";
export {
	cellAt,
	countEmpty,
	createBoard,
	emptyPositions,
	inBounds,
	isEmpty,
	place,
} from "./board.js";
export { type GameClient, LocalGameClient } from "./client.js";
export {
	applyMove,
	createGame,
	IllegalMoveError,
	isGameOver,
	requiredStones,
} from "./game.js";
export {
	findWinningLine,
	type MoveLegality,
	stonesRequired,
	validateMove,
} from "./rules.js";
export * from "./types.js";
