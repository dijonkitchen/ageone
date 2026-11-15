# Acceptance criteria

The old repo's acceptance criteria (its specs 0001 to 0005), carried over as [the spec](../specs/SPEC-2026-09-30-roi-rebuild.md) asks, plus criteria for what the spec adds: safety, the optional data adapter, and the research assistant.
Each has an ID; every test that checks one says so with `@pytest.mark.criteria("<ID>")`, and `tests/test_acceptance.py` fails if a criterion here has no test or a test cites an unknown one.

## Architecture

- **ARCH-1**: core modules (domain, ports, screening, strategy, execution, harness, pricing, analysis, research) import nothing from `adapters`.
- **ARCH-2**: the full test suite runs with no network access.
- **ARCH-3**: `uv run roi` screens a sample universe and prints an evaluation report.

## Safety

- **SAFE-1**: no code path can place a live order: the only `Broker` in the package is `PaperBroker`, and nothing imports a broker SDK.

## Screening

- **SCR-1**: a snapshot with fewer bars than a requested window raises `ValueError` rather than returning a misleading metric.
- **SCR-2**: `all_of()` with no filters passes everything; `any_of()` with no filters passes nothing.
- **SCR-3**: `Screener` returns only snapshots passing every filter.
- **SCR-4**: with a `score`, results are sorted descending and ties keep input order (stable sort).
- **SCR-5**: filters are pure: calling one never changes the snapshot.

## Trading and evaluation

- **TRD-1**: `PaperBroker` conserves value: cash plus position market value only changes through fills.
- **TRD-2**: each risk limit raises its own exception and leaves state unchanged.
- **TRD-3**: `backtest` is deterministic: the same inputs give an identical `EvalReport`.
- **TRD-4**: `max_drawdown` is non-negative, and `0.0` for a rising equity curve.

## Fundamentals, valuation, and allocation

- **FUN-1**: `parse_company_facts` maps a fixture payload to the right `Financials` and picks the latest annual (10-K) figures.
- **FUN-2**: the DCF matches a hand-computed example and rejects a discount rate at or below terminal growth.
- **FUN-3**: ratios return `None`, not a crash, on zero denominators.
- **FUN-4**: Kelly allocations are long-only, never exceed the total, and scale down when gross weight would exceed 1.
- **FUN-5**: the SEC adapter does no network I/O in tests (injected fetcher).
- **FUN-6**: `build_history` reports per-share metrics, year-over-year growth, and a median growth; growth is `None` when the prior value is not positive.
- **FUN-7**: `parse_company_facts_history` yields one record per fiscal year that has the required figures, newest within the last `years`.

## Options and stock price consistency

- **OPT-1**: Black-Scholes matches a known at-the-money value and satisfies put-call parity.
- **OPT-2**: implied volatility round-trips a model price and returns `None` when the price can't be reached.
- **OPT-3**: `parity_scan` flags only misaligned pairs and ignores unpaired contracts.
- **OPT-4**: `OptionQuote` rejects a security that isn't an option.

## Market data

- **DATA-1**: the optional live adapter (OpenBB) is an extra: importing and using the core and adapters never imports it, and the adapter maps its results to bars without a network in tests.

## Research assistant

- **RES-1**: the model is chosen by role from `harness/models.json`; no model ID appears in the code.
- **RES-2**: every company on the shortlist gets a summary, every sentence cites at least one source, and every citation is one of that company's sources; an answer that fails is rejected.
- **RES-3**: the assistant never places or suggests orders: it has no broker, its prompt forbids advice and treats sources as untrusted, and an answer that suggests an order, position, or price target is rejected.
- **RES-4**: an eval of it (`evals/cases/roi-cited-research`) runs through the harness runner, with the same prompt and checks as the code.
