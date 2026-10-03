# Output Formats

## Question

Which format should our tools use for data a model reads, and for data a model writes?
The [Agent Tool Interfaces](../../docs/decisions/2026-09-27-agent-tool-interfaces.md) record chose CSV for lists a model reads and NDJSON for data it writes, on token counts and outside results; this experiment checks that on our own cases.

## Setup

The same 30 tasks ([`data.json`](data.json)) are rendered in each format by [`generate`](generate), with the official TOON encoder for TOON.
Titles include commas, quotes, colons, and values that look like booleans or numbers, which is where formats break.

- Reading: three questions over all 30 tasks (sum a filtered column, count matching rows, find the row with the largest value), graded by exact answer.
- Writing: convert an 8-row Markdown table to the format, graded by parsing the answer (the official decoder for TOON) and comparing every field.

Each case is one model call with no harness or tools (`direct`), so the format is the only thing that changes.

## Conclusion

Not run yet: the runs need an OpenRouter key.

## Not measured

Nested data, lists longer than 30 rows, and formats inside an agent loop where the model also calls tools.
Token counts per format come from the runs' `tokens_in`, since every variant asks the same questions.
