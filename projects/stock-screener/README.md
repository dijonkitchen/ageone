# Stock screener

Screens US-listed companies on 10+ years of split-adjusted per-share history and ratios built from SEC EDGAR XBRL filings.
Spec: [SPEC-2026-10-03-stock-screener](../../specs/stock-screener/SPEC-2026-10-03-stock-screener.md).
Stack: [stock screener stack decision](../../docs/decisions/2026-10-03-stock-screener-stack.md).

Numbers come from company filings as tagged in SEC EDGAR XBRL data, may contain tagging errors, and are not investment advice.

## Setup

From the repo root, run `make` and then `make shell` for the pinned environment (Python and uv).
In this folder:

```sh
uv sync                              # installs the locked packages into .venv
cp config.example.toml config.toml   # then set user_agent to your name and email (the SEC requires it)
```

## Use

```sh
uv run screener refresh --tickers AAPL,MSFT,KO   # load a few companies
uv run screener refresh                          # every listed company; later runs load only new filings
uv run screener screen screens/compounders.toml  # table; --format csv|json, --out FILE
uv run screener company AAPL                     # yearly series, filings, splits, gaps
uv run screener app                              # the interactive page on http://localhost:8501
uv run screener columns                          # every screenable column and its definition
```

- `refresh --pit` keeps values as first reported (for backtests); the default lets restated values win.
  Switching reloads every company.
- `rebuild` recomputes metrics from stored statements after editing `metrics.toml`, without the network.
- `spot-check` compares loaded values with numbers from 10-K filings in `spot_check.toml`.
- `record-fixture TICKER` saves a company's Company Facts for offline tests.

## How it works

1. `sec.py` fetches the ticker list, each company's `submissions` (to see whether a new 10-K, 20-F, or 40-F, or an amendment, was filed since the last run), and `companyfacts` only for companies that changed.
   It sends the configured User-Agent, keeps under 10 requests per second, and backs off on errors.
2. `standardize.py` runs OpenBB's SEC provider on the Company Facts response for standardized annual statements, then adds the line items in [`gap_fill.toml`](src/screener/data/gap_fill.toml) (year-end shares, split ratios, and fallbacks), and records which filing each fiscal year came from.
3. `splits.py` finds splits as jumps in share counts between consecutive years (tagged ratios first, otherwise whole-number ratios) and adjusts the years before each jump, since filers restate only recent years.
4. `metrics.py` evaluates [`metrics.toml`](src/screener/data/metrics.toml), where every metric is defined once, then computes growth and consistency stats over 5, 10 (the latest year and the 10 before it), and all years.
5. `store.py` keeps everything in one DuckDB file; `screen.py` compiles a screen file to one SQL query, with `percent_rank()` for the composite score.

A screen file is TOML; see [`screens/compounders.toml`](screens/compounders.toml).
Columns are `metric.stat`, such as `bvps.cagr`, `roe.avg`, or `debt_to_equity.latest`.
The composite score is the weighted average of each chosen column's percentile rank (0 to 100) among the companies left after filtering; a company missing a column is ranked on the others, and `score_coverage` shows how much of the weight had data.

## Tests

`uv run pytest` runs on recorded fixtures with no network (see [`tests/fixtures`](tests/fixtures/README.md)), and CI runs it on every pull request that touches this folder.
