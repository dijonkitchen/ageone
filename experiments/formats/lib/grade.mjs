// Grader for the formats experiment.
//   grade.mjs read <expected answer> <answer file>
//   grade.mjs write <format> <expected.json> <answer file>
import { readFileSync } from "node:fs";
import { FORMATS, sameRecords } from "./formats.mjs";

// The model's answer without surrounding space or a Markdown code fence.
function answer(file) {
  return readFileSync(file, "utf8").trim().replace(/^```[a-z-]*\n([\s\S]*?)\n?```$/, "$1").trim();
}

const [mode, ...args] = process.argv.slice(2);
let problem;
if (mode === "read") {
  const [want, file] = args;
  const got = answer(file).replace(/[*`]/g, "").replace(/\.$/, "").trim();
  const numeric = !Number.isNaN(Number(want));
  problem = (numeric ? Math.abs(Number(got) - Number(want)) < 1e-9 && got !== "" : got === want) ? null : `expected ${want}, got ${JSON.stringify(got.slice(0, 200))}`;
} else if (mode === "write") {
  const [format, expected, file] = args;
  try {
    problem = sameRecords(await FORMATS[format].parse(answer(file)), JSON.parse(readFileSync(expected, "utf8")));
  } catch (err) {
    problem = `not valid ${FORMATS[format].label}: ${err.message.slice(0, 200)}`;
  }
} else {
  problem = `unknown mode ${mode}`;
}
if (problem) {
  console.log(`FAIL: ${problem}`);
  process.exit(1);
}
