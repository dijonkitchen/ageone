# Decision Record 2026-10-03: Stock Screener Stack

## Status timeline

2026-10-03: Proposed by Claude, at JC's request

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for the [stock screener](../../specs/SPEC-0007-stock-screener.md) and its [portfolio and Kelly allocation](../../specs/SPEC-0008-portfolio-kelly.md) that loads SEC EDGAR XBRL data for every filer, turns it into 10+ years of per-share series and ratios, screens all companies interactively, pulls live prices, and solves small portfolio optimizations.

#### Non-functional

Fast enough to screen every company in about a second on a laptop, local first, and installable in the pinned environment from [SPEC-0003](../../specs/SPEC-0003-make-setup.md).

### Nice to haves

#### Functional

Choice of price provider without code changes.

#### Non-functional

Few dependencies; a code base small enough for agents to change safely.

### Avoid out of scope runaway rabbit hole risks

#### Functional

Writing our own price provider integrations before one is needed.

#### Non-functional

A distributed or hosted data stack (warehouses, queues, cloud databases) for data that fits on one machine.

## Decision

- **Language**: Python, for the data and finance libraries.
- **Dataframes**: [Polars](https://pola.rs) (the Rust dataframe library with a Python API), not pandas, for loading, normalizing, and screening.
  pandas is used only where a library hands one back, and converted to Polars at that boundary.
- **Storage**: Parquet files on disk, read and written with Polars, one table per kind of data (facts, annual series, metrics, prices).
- **SEC data**: our own loader and normalizer, not OpenBB, because the specs need tag fallbacks, split adjustment, restatement handling, and filing traceability that a general data platform doesn't give.
- **Prices**: our own small provider interface, with the first adapter going through [OpenBB](https://github.com/OpenBB-finance/OpenBB) (Apache 2.0), so the user picks any provider OpenBB supports with their own API key.
- **Math**: NumPy for matrices and SciPy for the constrained Kelly solve (a small concave quadratic program).
  The Ledoit–Wolf shrinkage is a short function of our own, or scikit-learn's if it is already a dependency.
- **Local server**: a small Python HTTP API on `localhost` (such as FastAPI) that serves screen results, company data, prices, and allocations, and holds the API keys.
- **Front end**: a TypeScript single-page app, built with Vite, with a virtualized table for thousands of rows and a light charting library.
  The screen and allocation logic stays in Python; the page only renders and sends inputs.
- **Environment**: Python and its packages come from the pinned devenv environment (with `uv` for the lock file), next to the Node.js already there.

### High-level C4(context/container/component/code) diagram

```text
SEC EDGAR (bulk + APIs) --> loader/normalizer (Polars) --> Parquet files
Price provider --> OpenBB adapter --> price interface --> Parquet (history)
Parquet + live quotes --> local API (Python) --> TypeScript page (screen, company, portfolio)
```

### Choices and Tradeoffs/Risks

Polars over pandas: it is several times faster and lighter on memory on the full set of filers (tens of millions of facts), its lazy queries and native Parquet fit the storage, and its stricter API leaves fewer silent type and index mistakes.
The cost is fewer examples and libraries that expect pandas, handled by converting at the boundary.

Our own SEC pipeline over OpenBB's SEC provider: OpenBB is good at fetching data from many providers, but the hard part of this project is normalizing XBRL into comparable 10-year per-share series, which we need to own and test.

OpenBB for prices over writing provider adapters: it gives many providers at once, behind keys the user already has.
The cost is a large dependency tree; if it causes install or version trouble, a direct adapter for one provider replaces it behind the same interface.

A local Python server over a static page: live prices need API keys that must not reach the browser, and Python owns the data and math.

### Dependencies

Polars, NumPy, SciPy, OpenBB, a Python HTTP framework, Vite, and TypeScript, all pinned in the devenv environment.

### Interfaces

- Price provider: `quote(tickers) -> table` and `history(tickers, start, end) -> table` with ticker, timestamp, price, currency, source, and delay.
- Screen file and portfolio file: plain text, defined in SPEC-0007 and SPEC-0008.

## Key Results and retrospective feedback
