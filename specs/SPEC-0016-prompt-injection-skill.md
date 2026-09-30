# SPEC-0016: Prompt Injection Skill

Restarts [dijonkitchen/skills](https://github.com/dijonkitchen/skills)'s prompt-injection-prevention skill in `skills/prompt-injection-prevention/`, per [Projects in ageone](../docs/decisions/2026-09-30-projects-in-ageone.md), so every project that feeds untrusted text to a model uses one defense.

## Functional requirements

- An agent-agnostic `SKILL.md` telling agents how to design and review LLM features that read untrusted data, following the CaMeL approach: keep untrusted data out of control flow, tag data with its source, and gate tool calls behind explicit capabilities.
- A small library the projects can call: source tags on text, a capability check before a tool call, and a quarantined model call that returns only structured data.
- An eval of the library against a set of known injection payloads through the runner from [SPEC-0002](SPEC-0002-vendor-neutral-ai-harness.md).

## Non-functional requirements

- Works in any harness: plain Markdown instructions plus a library with no required network.
- Honest: the skill says what it doesn't protect against; pattern matching is a warning, not a defense.

## Definition of done

1. The skill and library are in `skills/prompt-injection-prevention/`, with tests passing in CI.
2. The eval's results appear on the SPEC-0004 pages.
3. At least one project (aiprofile, needle, or sonal) uses it.
