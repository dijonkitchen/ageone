import { expect, test } from "bun:test";
import { greet } from "./index";

test("greet names who it greets", () => {
	expect(greet("ageone")).toBe("Hello, ageone!");
});
