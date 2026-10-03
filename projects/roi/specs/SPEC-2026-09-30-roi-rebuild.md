# SPEC-2026-09-30-roi-rebuild: ROI Rebuild

Restarts [dijonkitchen/roi](https://github.com/dijonkitchen/roi) in this folder, `projects/roi/`, per [Projects in ageone](../../../docs/decisions/2026-09-30-projects-in-ageone.md): the old repo is a reference only, and decision records start fresh in `projects/roi/docs/decisions/`.

A toolkit to screen stocks and options and evaluate strategies offline, shaped as ports and adapters so real data feeds and, much later, brokers plug in without a rewrite.

## Functional requirements

- A deterministic core with no I/O: securities, bars, snapshots with derived metrics, composable screening filters, strategies that emit signals, and a paper broker enforcing risk limits.
- A backtest harness producing an evaluation report (return, maximum drawdown, trades), carrying over the old repo's screening, trading, fundamentals, and options-alignment acceptance criteria.
- Market data behind a port: sample data for tests, and an optional adapter for live prices (the old repo used OpenBB).
- An LLM research assistant that picks its model by role through the model roles config from [SPEC-2026-09-26-vendor-neutral-ai-harness](../../../specs/SPEC-2026-09-26-vendor-neutral-ai-harness.md), never a model ID in code and summarizes a shortlist's filings and news, each summary citing its sources; it never places or suggests orders.

## Non-functional requirements

- Safe by default: no code path can place a live order.
- Offline tests: the core and harness need no network.
- The optional data adapter doesn't slow down or break the core install.

## Definition of done

1. The first decision record in `projects/roi/docs/decisions/` chooses the stack (old: Python, uv, pytest, hexagonal architecture, optional OpenBB).
2. `projects/roi/` is set up by `make`, and its CI job passes on `main`.
3. Screening, backtesting, and paper trading pass tests citing their acceptance criteria.
4. The demo command screens a sample universe and backtests it offline.
5. The research assistant produces cited summaries for a sample shortlist, and an eval of it runs through the SPEC-2026-09-26-vendor-neutral-ai-harness runner.
