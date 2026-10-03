# Decision Record 2026-10-03: Stock Screener Stack

## Status timeline

2026-10-03: Proposed by Claude, at JC's request

2026-10-03: Accepted by JC

2026-10-03: Amended by Claude, implementing the spec: record the storage format, the pinned OpenBB version, the gap-filling tag mapping, and where the code lives, from the first implementation.

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for the [stock screener](../../specs/stock-screener/SPEC-2026-10-03-stock-screener.md) and its [portfolio and Kelly allocation](../../specs/stock-screener/SPEC-2026-10-03-portfolio-kelly.md) that loads SEC EDGAR XBRL data for every filer, turns it into 10+ years of per-share series and ratios, screens all companies interactively, pulls live prices, and solves small portfolio optimizations.

#### Non-functional

Fast enough to screen every company in about a second on a laptop, local first, and installable in the pinned environment from [SPEC-2026-09-26-make-setup](../../specs/SPEC-2026-09-26-make-setup.md).

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

### Implementation details

- **Code**: [`projects/stock-screener/`](../../projects/stock-screener/), a uv project with its own `uv.lock`; Python 3.12 comes from devenv.
- **OpenBB**: `openbb-sec==2.0.0` and `openbb-core==2.0.1`, pinned in `pyproject.toml`.
  We call its `resolve_company_facts` on Company Facts responses we fetch ourselves, so the SEC client (User-Agent, rate limit, backoff) and the change check stay ours.
  A test compares its output on a recorded real filer with a recording, so an upgrade that changes numbers fails until reviewed.
- **Storage format**: one DuckDB file (`screener.duckdb`, git-ignored) with tables `companies`, `line_items` (OpenBB's standardized annual line items plus gap fills, each with its source), `filings` (the filing behind each fiscal year), `split_facts`, `splits`, `metric_values` (one row per company, year, and metric), `stats` (per window, metric, and stat), and `gaps`.
  Raw Company Facts responses are not kept; `rebuild` recomputes metrics from `line_items`.
- **Gap-filling tag mapping**: [`gap_fill.toml`](../../projects/stock-screener/src/screener/data/gap_fill.toml) maps each missing line item to an ordered list of XBRL concepts (year-end shares outstanding, interest expense, dividends declared per share, and split ratios).
- **Metric definitions**: [`metrics.toml`](../../projects/stock-screener/src/screener/data/metrics.toml), formulas over line items and named inputs.

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
The costs are a dependency on its schema and correctness, handled by pinning its version, recording fixtures of its output for our tests, and spot checking against filings on each upgrade; its restatement rule, which takes the latest annual filing within 450 days of a year end, so a restatement two filings later is not used; and fetching company by company instead of from the nightly bulk file, which is slower for a first full load but fine within the SEC's 10 requests per second.

OpenBB for prices over writing provider adapters: it gives many providers at once, behind keys the user already has.
The cost is a large dependency tree; if it causes install or version trouble, a direct adapter for one provider replaces it behind the same interface.

Streamlit over a TypeScript single-page app with a Python API: one language, no build step, no HTTP API to design or keep in sync, and API keys never reach the browser.
The cost is less control over layout and interaction, and a page that reruns its script on each input, which is fast enough for one local user on this data size.
If the UI outgrows it, a later decision record can move the front end to TypeScript on top of the same Python functions.

### Dependencies

DuckDB, pandas, NumPy, SciPy, OpenBB (its SEC provider and a price provider extension), and Streamlit, all pinned in the devenv environment.

### Interfaces

- Price provider: `quote(tickers) -> table` and `history(tickers, start, end) -> table` with ticker, timestamp, price, currency, source, and delay.
- Screen file and portfolio file: plain text, defined in SPEC-2026-10-03-stock-screener and SPEC-2026-10-03-portfolio-kelly.

## Key Results and retrospective feedback
