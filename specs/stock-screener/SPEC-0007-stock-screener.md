# SPEC-0007: Stock Screener

## Functional requirements

A stock screener for US-listed companies that pulls the latest public filing data from the SEC, builds 10 or more years of per-share history for each company, and sorts, filters, and ranks companies by growth, per-share metrics, and ratios.

- **Data source**: SEC EDGAR's free structured XBRL data ([Company Facts](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)), with no paid data vendor, read through [OpenBB](https://github.com/OpenBB-finance/OpenBB)'s SEC provider.
  - OpenBB turns Company Facts into standardized annual balance sheets, income statements, and cash flow statements: it maps over a thousand XBRL tags to a fixed set of line items, picks a layout for industrial companies, banks, insurers, and REITs, checks accounting identities, and records where each value came from.
    We build on those standardized statements instead of mapping XBRL tags ourselves.
  - The `submissions` API on `data.sec.gov` tells us which companies filed since the last refresh, and the ticker-to-CIK map (`company_tickers_exchange.json`) lets companies be looked up by ticker.
  - XBRL starts in 2009 to 2011 depending on filer size, so most companies have about 15 years of annual data; earlier years are out of scope (see below).
- **Refresh**: one command pulls what changed since the last run, using filing dates from `submissions`, so a 10-K filed today shows up after the next refresh.
  Standardized statements are cached on disk as Parquet, so a refresh with nothing new makes no data requests beyond the change check, and screening never waits on the network.
  Each company records the accession number and filing date of the latest filing used, so every number traces back to a filing.
- **Annual series**: for each company, one value per fiscal year per line item, from OpenBB's standardized annual statements.
  - When a later filing restates a year, the latest filed value wins by default; an option uses OpenBB's point-in-time mode to keep the value as first reported, to avoid look-ahead in backtests.
  - Where a metric needs a line item the standardized statements don't have, a small mapping file (line item to an ordered list of XBRL tags, read from Company Facts) fills the gap; it stays data, not code.
  - Values reported in other currencies (20-F, 40-F filers) keep their currency and are flagged; no FX conversion for now.
  - A missing year stays missing; nothing is interpolated beyond what OpenBB derives and labels as derived.
- **Per-share values**: each value divided by the diluted weighted average shares for flow items (income, cash flow) and by shares outstanding at fiscal year end for balance-sheet items (book value), adjusted for stock splits so a 10-year series is comparable.
  Splits come from the split ratio tags where tagged, otherwise from detecting a jump in share count that matches a whole-number ratio between consecutive filings.
- **Metrics**, each as a yearly series for at least 10 fiscal years where the data exists:
  - Per share: book value (BVPS), tangible book value, diluted EPS, revenue, operating cash flow, free cash flow (operating cash flow minus capital expenditure), and dividends.
  - Profitability: return on equity, return on assets, return on invested capital, and gross, operating, and net margins.
  - Balance sheet: debt to equity, current ratio, and interest coverage.
  - Each metric is defined once (formula, inputs, and the concepts it uses) in a definitions file, and shown with its definition in the UI and exports.
- **Growth and consistency** over a chosen window (5, 10, or all available years, default 10):
  - Compound annual growth rate (CAGR) of each per-share series, such as 10-year BVPS growth.
    A start or end value at or below zero has no CAGR and is marked so, rather than giving a misleading number.
  - Consistency: the number of years the value grew, the longest growth streak, the standard deviation of yearly growth, and the R² of a log-linear fit, so steady compounders stand out from lucky endpoints.
  - Averages and medians of each ratio over the window, such as 10-year average ROE.
- **Screening**:
  - Filter by any metric with thresholds (such as 10-year BVPS CAGR ≥ 10% and debt to equity ≤ 0.5), by minimum years of data, and by exchange, SIC industry, and fiscal year end recency (to drop companies that stopped filing).
  - Sort by any column, ascending or descending.
  - Rank by a composite score: a weighted sum of each chosen metric's percentile rank across the companies left after filtering, with the weights and direction (higher or lower is better) set per metric.
  - Screens save to and load from a plain-text file (filters, sort, and composite weights), so a screen can be rerun after a refresh and diffed.
- **Interfaces**:
  - A command-line tool that refreshes data, runs a saved screen, and prints a table or writes CSV or JSON.
  - An interactive local web page: build a screen by adding and removing filters, dragging threshold sliders, choosing columns, and setting composite weights, with the results table re-sorting and re-ranking as you change them, and save or load the screen file from the page.
  - A company page that charts each per-share series and ratio over the years and lists the filings it came from.
  - Rows can be selected, so [SPEC-0008](SPEC-0008-portfolio-kelly.md) can build a portfolio from a screen.
- **Data gaps**: each company and metric shows how many years are present and which concepts were missing, so a gap reads as missing data instead of a zero or a bad rank.

## Non-functional requirements

- Follows the [SEC's fair access rules](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data): a `User-Agent` header with a contact email set in local config (never committed), at most 10 requests per second, and backoff on errors.
- Local first: data lives in a folder of columnar files on disk, served by a local process on `localhost`; no hosted server, account, or cloud service.
  A full load of all filers fits on a laptop and finishes in under an hour; screening all companies takes under a few seconds.
- Correct: metric formulas, split adjustment, the gap-filling tag mapping, restatement handling, and CAGR edge cases are covered by tests that run on small recorded fixtures of real standardized statements and Company Facts responses, with no network in tests.
  OpenBB is pinned to a version, and its standardized output is checked against the spot check below when it is upgraded.
  A spot check compares 10 years of BVPS and EPS for a handful of well-known companies against their 10-K filings.
- Deterministic: the same downloaded data and screen file give the same results.
- Not financial advice: the UI and exports say the numbers come from company filings as tagged, may contain tagging errors, and are not investment advice.
- Stack as in the [stock screener stack decision](../../docs/decisions/2026-10-03-stock-screener-stack.md): Python with Polars, Parquet files, and a small TypeScript front end.
- Runs in the pinned environment from [SPEC-0003](../SPEC-0003-make-setup.md), with no global installs.

### Out of scope

- Years before XBRL (pre-2009), which would mean parsing HTML or text filings.
- Stock prices and price-based ratios (P/E, P/B, dividend yield, earnings yield), since the SEC doesn't publish prices.
  [SPEC-0008](SPEC-0008-portfolio-kelly.md) adds them; the metric definitions file leaves room for price inputs.
- Quarterly or trailing-twelve-month series (OpenBB has them; screening on them can come later), FX conversion, alerts, and backtesting.
- Our own XBRL-to-statement normalization, which OpenBB already does.

## Definition of done

1. One command does a full load from SEC EDGAR and a second refresh picks up only new filings, with cached downloads and the fair access rules followed.
2. For any company with the data, the tool shows at least 10 fiscal years of split-adjusted BVPS, EPS, revenue, free cash flow, and dividends per share, plus the ratios above, each traced to its filing.
3. A saved screen filters, sorts, and ranks all companies by a composite score, from the command line (table, CSV, JSON) and interactively on the local web page, with a company page charting each series.
4. Tests cover the formulas and edge cases above on recorded fixtures and run in CI, and the spot check matches the filings for the chosen companies.
5. The stack decision record is accepted, and states the storage format, the pinned OpenBB version, and the gap-filling tag mapping.
