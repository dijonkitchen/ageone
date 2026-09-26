# SPEC-0002: Vendor-Neutral AI Harness With Evals

## Functional requirements

Run agentic work in this repo through a harness that is not tied to one model vendor, so a newly released model can be tried the day it ships and the cheapest model that still passes can be the default.

- Switching the model is a one-line config change, never a code change. Roles (`default`, `cheap`, `frontier`, `judge`) map to `provider/model` IDs in one checked-in file.
- At least these providers work: Anthropic direct, OpenAI direct, Google direct, AWS Bedrock (for Claude and open-weight models under AWS IAM and billing), and one OpenAI-compatible endpoint (a gateway such as LiteLLM or OpenRouter, or a local server such as Ollama).
- Prompts, skills, and instructions live in the repo as plain files (`AGENTS.md`, `specs/`, `docs/decisions/`), not inside any vendor's product, so any harness can read them.
- An eval suite built from this repo's own tasks runs on demand and on every model, prompt, or harness change. It reports pass rate, cost per completed task, tokens, turns, and wall-clock time per model, with more than one repetition per case.
- Eval cases are sourced from real sessions: completed tasks become regression cases, failures become new cases. Results are committed so trends are visible over time.

## Non-functional requirements

- Simple: one harness, one config file, one eval command. No orchestration framework until measurement says one is needed.
- Portable: everything is text in the repo. Harness swap (for example pi to OpenCode) loses nothing but the harness's own config file.
- Honest measurement: infra failures, truncation, and refusals are recorded separately from model failures; the served model is asserted on every call; a reference solution and a null baseline are run through the grader before trusting numbers.
- Cheap by default: prompt caching on, effort tuned per role, batch or slow tiers for parallel offline work.

## Definition of done

1. A model-roles config file exists in the repo and the chosen harness reads it; changing `default` to a different provider's model and running one task works with no other edit.
2. Tasks run end to end on at least three providers, one of which is AWS Bedrock.
3. `evals/` holds at least ten cases drawn from this repo's own tasks, a runner, and a results file per model run with the metrics above.
4. The eval has been run against at least two models and the decision record for this spec records which model is the default and why.
