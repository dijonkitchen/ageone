# Decision Record 2026-09-20: Cache Policy

## Status timeline

2026-09-20: Proposed by JC

## Objective Context

Agent loops re-read the same prefix on every turn. Caching that prefix is the largest saving we have, and it costs nothing to turn on.

## Decision

Put tools, the system prompt, and AGENTS.md first. Put volatile content last, so the prefix stays stable. Measure the cache hit rate in every eval run!

Caches are scoped to one model. Does a cascade lose them? Yes, so escalate only after two failures.

```
keep this line. It is code.
```
