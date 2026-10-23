// Accuracy of the model classifier against the old word list on the hand-labeled set.
// Needs OPENROUTER_API_KEY. Pass --append to add a line to results/accuracy.jsonl.
//   bun run src/eval.ts [role ...]      (default: cheap default)
import { appendFileSync, mkdirSync } from "node:fs";
import { baselineAccuracy, type Labeled, modelAccuracy } from "./accuracy.ts";
import labeled from "./fixtures/labeled.json";
import { openRouterChat } from "./model.ts";

const args = process.argv.slice(2);
const append = args.includes("--append");
const roles = args.filter((a) => !a.startsWith("--"));
const set = labeled as Labeled[];
const baseline = baselineAccuracy(set);
console.log(`word list: ${baseline.toFixed(2)}`);
for (const role of roles.length ? roles : ["cheap", "default"]) {
	const accuracy = await modelAccuracy(openRouterChat(role), set);
	console.log(`${role}: ${accuracy.toFixed(2)}`);
	if (append) {
		mkdirSync("results", { recursive: true });
		appendFileSync(
			"results/accuracy.jsonl",
			`${JSON.stringify({ date: new Date().toISOString().slice(0, 10), role, n: set.length, accuracy, baseline })}\n`,
		);
	}
}
