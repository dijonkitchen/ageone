# SPEC-0002: Vendor-Neutral AI Harness With Evals

## Functional requirements

Run agentic work in this repo through a harness that is not tied to one model vendor, so a newly released model can be tried the day it ships and the cheapest model that still passes can be the default.

- Switching the model is a one-line config change, never a code change. Roles (`default`, `cheap`, `frontier`, `judge`) map to `provider/model` IDs in one checked-in file.
  pi reads models from project `.pi/settings.json` (`defaultProvider`, `defaultModel`) and `--model`; its `models.json` is user-level only (`~/.pi/agent/`), so the roles file is ours and scripts pass each role to pi with `--model`.
- OpenRouter is the default access for all roles (Claude, GPT, Gemini, and open-weight models on one key), with zero data retention enforced account-wide. At least one vendor API direct also works, so leaving the gateway is a config change.
- Web search and page fetch work in the harness. pi ships only `read`, `bash`, `edit`, and `write`, with no web search and no MCP, so a search extension is declared in project `.pi/settings.json` and covered by an eval case.
- Open-weight models (including Chinese-lab models such as DeepSeek, Qwen, Kimi, GLM) run only on hosts that neither train on nor retain prompts: US or EU inference providers, reached through OpenRouter with zero data retention and an allowlist of hosts. China-based hosts, including the labs' own APIs, are not used for this repo's work.
- Prompts, skills, and instructions live in the repo as plain files (`AGENTS.md`, `specs/`, `docs/decisions/`), not inside any vendor's product, so any harness can read them.
- An eval suite built from this repo's own tasks runs on demand and on every model, prompt, or harness change. It reports pass rate, cost per completed task, tokens, turns, and wall-clock time per model, with more than one repetition per case.
- Eval cases are sourced from real sessions: completed tasks become regression cases, failures become new cases. Results are committed so trends are visible over time.

## Non-functional requirements

- Simple: one harness, one config file, one eval command. No orchestration framework until measurement says one is needed.
- Portable: everything is text in the repo. Harness swap (for example pi to OpenCode) loses nothing but the harness's own config file.
- Honest measurement: infra failures, truncation, and refusals are recorded separately from model failures; the served model is asserted on every call; a reference solution and a null baseline are run through the grader before trusting numbers.
- Cheap by default: prompt caching on, effort tuned per role, batch or slow tiers for parallel offline work.
- Private by default: provider data policies (no training, zero or short retention) are checked before a provider is added, and enforced in config where the provider allows it.

## Definition of done

1. A model-roles config file exists in the repo and the chosen harness uses it; changing `default` to a different provider's model and running one task works with no other edit.
2. Tasks run end to end on OpenRouter and on one vendor API direct, and one task runs on a Chinese-lab open-weight model served only by an allowlisted US or EU host.
3. A task that needs the web (search, then fetch a page and cite it) completes in pi.
4. `evals/` holds at least ten cases drawn from this repo's own tasks, a runner, and a results file per model run with the metrics above.
5. The eval has been run against at least two models and the decision record for this spec records which model is the default and why.
