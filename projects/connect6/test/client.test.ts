import { describe, expect, it } from "bun:test";
import { IllegalMoveError, LocalGameClient } from "../src/core/index.js";

describe("LocalGameClient (REQ-CLIENT)", () => {
	it("AC-CLIENT-1: exposes async getState / applyMove / reset", async () => {
		const client = new LocalGameClient();

		const initial = await client.getState();
		expect(initial.toMove).toBe("black");
		expect(initial.moveCount).toBe(0);

		const afterMove = await client.applyMove({
			positions: [{ row: 9, col: 9 }],
		});
		expect(afterMove.toMove).toBe("white");
		expect(afterMove.moveCount).toBe(1);

		const reset = await client.reset();
		expect(reset.toMove).toBe("black");
		expect(reset.moveCount).toBe(0);
	});

	it("AC-CLIENT-2: rejects illegal moves with the core's error", async () => {
		const client = new LocalGameClient();
		// Opening move must be a single stone; two stones is illegal.
		await expect(
			client.applyMove({
				positions: [
					{ row: 0, col: 0 },
					{ row: 0, col: 1 },
				],
			}),
		).rejects.toThrow(IllegalMoveError);
	});
});
