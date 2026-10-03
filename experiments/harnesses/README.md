# Harnesses

## Question

Which harness completes this repo's own tasks best for the cost: pi or Claude Code?
The [Vendor-Neutral AI Harness](../../docs/decisions/2026-09-26-vendor-neutral-ai-harness.md) record chose pi for being small, scriptable, and vendor neutral; this experiment measures what that choice costs or saves on our tasks.

## Setup

Both harnesses run every case in [`evals/cases`](../../evals/cases) with the same models, reached through OpenRouter, in the same fresh sandbox per case.
pi runs with its four tools plus the pinned web search extension; Claude Code runs with its own built-in tools.
Direct cases run with tools turned off in both.

## Conclusion

Not run yet: the runs need an OpenRouter key.

## Not measured

OpenCode, which is next once it has an adapter.
Interactive use, IDE integration, and tasks longer than one prompt.
Claude Code's web search goes through Anthropic's server-side tool, which OpenRouter may not pass through for every model, so the web case measures each harness's web access as shipped.
