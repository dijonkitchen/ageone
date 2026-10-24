# Decision Record 2026-10-04: Prompt Injection Library

## Status timeline

2026-10-04: Proposed by Claude, implementing [SPEC-2026-09-30-prompt-injection-skill](../../../../specs/SPEC-2026-09-30-prompt-injection-skill.md)

## Objective Context

### Simple, lovable, complete must haves

#### Functional

One defense, shared by every project that feeds untrusted text to a model: source tags on values, a capability check before each tool call, and a quarantined model call that returns only structured data.

#### Non-functional

Works in any harness and with any model, with no required network or dependencies, and says plainly what it doesn't protect against.

### Nice to haves

#### Functional

A TypeScript port for browser projects, once one adopts the skill.

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

A full CaMeL interpreter that runs a privileged model's plan as code and tracks data flow through it.

Injection classifiers or detection models.

#### Non-functional

## Decision

Rebuild the old skill from [dijonkitchen/skills](https://github.com/dijonkitchen/skills) as a much smaller library around the four CaMeL rules in [SKILL.md](../../SKILL.md):

- `Value`: a value with its `sources` and `readers`, and `derive` to carry both into anything computed from it.
- `Policy`: tools are denied unless granted; each grant lists rules over the tagged arguments.
- `extract`: the quarantined call, whose prompt marks the text as data inside markers the text can't close, and whose reply must parse as JSON with exactly the schema's keys and types (`Bool`, `Int`, `Choice`, `Text`).
- `injection_warnings`: pattern matching, documented as a warning only.

Python (standard library only, 3.11+), from the template's Python stack with `make check`.
The old repo was Python too, and the code is small enough to port to TypeScript when a Bun project needs it.

The old library's input sanitizer decided ALLOW, DENY, or QUARANTINE from pattern matches, and its policy engine keyed decisions off threat levels.
Both made pattern matching part of the defense, which the spec rules out, so they are dropped; the taint tracker, capability manager, and dual-LLM orchestrator become `Value`, `Policy`, and `extract`.

The eval is the [prompt injection experiment](../../../../experiments/prompt-injection/): one invoice with eight payloads, extracted with the library's prompt and with a plain prompt, so the eval pages show how often injected text changes the data.
Tool misuse isn't in the experiment because the policy blocks it without a model; the unit tests cover it.

### High-level C4(context/container/component/code) diagram

### Choices and Tradeoffs/Risks

Explicit tagging over automatic taint tracking through Python operations: wrapping `str` and friends catches more, but leaks through any library call that returns a plain value, and makes code harder to read.
With `derive`, the caller tags results by hand, so a missed `derive` drops taint; reviews check for it, per the skill's checklist.

`extract` returns fields tagged untrusted, even narrow ones like `Bool`, because an injection can still choose their values.

### Dependencies

[SPEC-2026-09-30-projects-scaffold](../../../../specs/SPEC-2026-09-30-projects-scaffold.md) for the template and CI, and the eval runner from [SPEC-2026-09-26-vendor-neutral-ai-harness](../../../../specs/SPEC-2026-09-26-vendor-neutral-ai-harness.md).

### Interfaces

The names exported from `prompt_injection_prevention`, documented in [SKILL.md](../../SKILL.md).

## Key Results and retrospective feedback
