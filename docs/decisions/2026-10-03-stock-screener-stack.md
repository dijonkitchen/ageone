# Decision Record 2026-10-03: Stock Screener Stack

## Status timeline

2026-10-03: Proposed by Claude, at JC's request

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for the [stock screener](../../specs/stock-screener/SPEC-0007-stock-screener.md) and its [portfolio and Kelly allocation](../../specs/stock-screener/SPEC-0008-portfolio-kelly.md) that loads SEC EDGAR XBRL data for every filer, turns it into 10+ years of per-share series and ratios, screens all companies interactively, pulls live prices, and solves small portfolio optimizations.

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

- **Language**: Python only, back end and front end, for the data and finance libraries and so one person or agent can change any part.
- **Storage and screening**: [DuckDB](https://duckdb.org), one embedded database file holding the standardized statements, per-share series, metrics, and daily price history.
  Screens run as SQL (filters, sorts, and `percent_rank()` for the composite score), and a saved screen file compiles to one query.
- **Dataframes**: pandas, the library OpenBB already returns, for per-company work that reads better as code than SQL (split detection, growth and consistency series).
  DuckDB reads and writes pandas DataFrames directly, so there is no conversion layer.
- **SEC data**: [OpenBB](https://github.com/OpenBB-finance/OpenBB)'s SEC provider (Apache 2.0), pinned to a version, for standardized annual statements built from Company Facts, including its point-in-time mode for as-first-reported values.
  Our own code adds what it doesn't do: split adjustment, per-share series, metrics, growth and consistency, screening, and a small gap-filling tag mapping for any line item a metric needs that the standard statements lack.
- **Prices**: our own small provider interface, with the first adapter also going through OpenBB, so the user picks any provider OpenBB supports with their own API key.
- **Math**: NumPy for matrices and SciPy for the constrained Kelly solve (a small concave quadratic program).
  The Ledoit–Wolf shrinkage is a short function of our own, or scikit-learn's if it is already a dependency.
- **Front end**: [Streamlit](https://streamlit.io), a Python app on `localhost` that gives the interactive table, sliders, inputs, and charts, and can rerun part of a page on a timer for live quotes.
  API keys stay in the Python process; the browser only gets the rendered page.
- **Environment**: Python and its packages come from the pinned devenv environment, with `uv` for the lock file.

### High-level C4(context/container/component/code) diagram

```text
SEC EDGAR Company Facts --> OpenBB SEC provider (standardized statements) --> per-share, metrics (pandas) --> DuckDB file
Price provider --> OpenBB adapter --> price interface --> DuckDB file (daily history)
DuckDB file (screens as SQL) + live quotes --> Streamlit app on localhost (screen, company, portfolio)
```

### Choices and Tradeoffs/Risks

pandas over Polars: once OpenBB normalizes the filings, the data is small (about 6,000 companies × 15 years × a few hundred line items, and a screen table of about 6,000 rows), so Polars' speed buys nothing users would notice, and OpenBB already speaks pandas.
The one large table, daily prices (about 6,000 companies × 15 years × 252 days, over 20 million rows), lives in DuckDB, which queries it on disk without loading it into memory.
Polars stays an option for a hot spot a profile shows, since DuckDB reads its frames too.

DuckDB over plain Parquet files: one file to back up instead of a folder, SQL for screens and ranks that people and agents read easily, and joins with price history without loading it.
The cost is SQL next to pandas, kept apart: SQL for set-wide queries (screens, ranks, joins), pandas for per-company series.

OpenBB's SEC provider over our own XBRL normalizer: turning Company Facts into comparable statements (tag changes across taxonomy years, banks and insurers, restatements, accounting identities) is the hardest part of the screener, and OpenBB already does it with a documented method and a large validation set.
The costs are a dependency on its schema and correctness, handled by pinning its version, recording fixtures of its output for our tests, and spot checking against filings on each upgrade; and fetching company by company instead of from the nightly bulk file, which is slower for a first full load but fine within the SEC's 10 requests per second.

OpenBB for prices over writing provider adapters: it gives many providers at once, behind keys the user already has.
The cost is a large dependency tree; if it causes install or version trouble, a direct adapter for one provider replaces it behind the same interface.

Streamlit over a TypeScript single-page app with a Python API: one language, no build step, no HTTP API to design or keep in sync, and API keys never reach the browser.
The cost is less control over layout and interaction, and a page that reruns its script on each input, which is fast enough for one local user on this data size.
If the UI outgrows it, a later decision record can move the front end to TypeScript on top of the same Python functions.

### Dependencies

DuckDB, pandas, NumPy, SciPy, OpenBB (its SEC provider and a price provider extension), and Streamlit, all pinned in the devenv environment.

### Interfaces

- Price provider: `quote(tickers) -> table` and `history(tickers, start, end) -> table` with ticker, timestamp, price, currency, source, and delay.
- Screen file and portfolio file: plain text, defined in SPEC-0007 and SPEC-0008.

## Key Results and retrospective feedback
