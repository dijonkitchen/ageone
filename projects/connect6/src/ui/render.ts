/**
 * Pure-ish view layer: given a GameState and the pending selection, draw the
 * board. The renderer knows nothing about how moves are produced — it only
 * reports clicks back through a callback (constitution §3).
 */

import {
	cellAt,
	type GameState,
	type Position,
	positionKey,
} from "../core/index.js";

export type CellClickHandler = (pos: Position) => void;

export const renderBoard = (
	container: HTMLElement,
	state: GameState,
	pending: readonly Position[],
	onCellClick: CellClickHandler,
): void => {
	const { size, board } = state;
	container.style.setProperty("--size", String(size));

	const pendingKeys = new Set(pending.map(positionKey));
	const winKeys = new Set((state.winningLine ?? []).map(positionKey));

	const fragment = document.createDocumentFragment();
	for (let row = 0; row < size; row += 1) {
		for (let col = 0; col < size; col += 1) {
			const pos: Position = { row, col };
			const key = positionKey(pos);
			const occupant = cellAt(board, pos);

			const cell = document.createElement("button");
			cell.type = "button";
			cell.className = "cell";
			cell.setAttribute("aria-label", `row ${row + 1}, column ${col + 1}`);

			if (occupant) {
				const stone = document.createElement("span");
				stone.className = `stone ${occupant}${winKeys.has(key) ? " win" : ""}`;
				cell.appendChild(stone);
				cell.disabled = true;
			} else if (pendingKeys.has(key)) {
				const stone = document.createElement("span");
				stone.className = `stone ${state.toMove} pending`;
				cell.appendChild(stone);
			}

			cell.addEventListener("click", () => onCellClick(pos));
			fragment.appendChild(cell);
		}
	}

	container.replaceChildren(fragment);
};
