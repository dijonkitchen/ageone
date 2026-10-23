# Stock screener

Screens US-listed companies on 10+ years of split-adjusted per-share history and ratios built from SEC EDGAR XBRL filings.
Spec: [SPEC-2026-10-03-stock-screener](specs/SPEC-2026-10-03-stock-screener.md).
Stack: [stock screener stack decision](docs/decisions/2026-10-03-stock-screener-stack.md).

Live prices, price ratios, and a portfolio page that sizes positions by fractional Kelly come from [SPEC-2026-10-03-portfolio-kelly](specs/SPEC-2026-10-03-portfolio-kelly.md).

Numbers come from company filings as tagged in SEC EDGAR XBRL data, may contain tagging errors, and are not investment advice.
A Kelly allocation is the mathematical result of your own return assumptions, not advice.

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
uv run screener quotes KO AAPL                   # live quotes with time, source, and delay (cached)
uv run screener ratios KO                        # live ratios, and P/E, P/B, P/FCF, yield at each 10-K date
uv run screener screen my.toml --quotes          # screen on live.* columns from the cached quotes
uv run screener portfolio my-portfolio.toml      # fractional Kelly weights, dollars, whole shares, trades
```

- `refresh --pit` keeps values as first reported (for backtests); by default the latest 10-K wins, however many years after it restated a value (OpenBB alone stops at 450 days, so `standardize.py` hands it the latest annual value for every period first).
  Switching reloads every company.
- `rebuild` recomputes metrics from stored statements after editing `metrics.toml`, without the network.
- `spot-check` compares loaded values with numbers from 10-K filings in `spot_check.toml`.
- `record-fixture TICKER` saves a company's Company Facts for offline tests.
- Prices come through OpenBB's yfinance provider by default (no key, delayed); set another installed provider and its keys under `[prices]` in `config.toml`.
  `--prices-dir DIR` reads recorded quotes and history instead (saved by `record-prices`), for working offline.
- Historical price ratios need each year's first filing date, which databases loaded before prices existed lack until `refresh --full`.

## How it works

1. `sec.py` fetches the ticker list, each company's `submissions` (to see whether a new 10-K, 20-F, or 40-F, or an amendment, was filed since the last run), and `companyfacts` only for companies that changed.
   It sends the configured User-Agent, keeps under 10 requests per second, and backs off on errors.
2. `standardize.py` runs OpenBB's SEC provider on the Company Facts response for standardized annual statements, then adds the line items in [`gap_fill.toml`](src/screener/data/gap_fill.toml) (year-end shares, split ratios, and fallbacks), and records which filing each fiscal year came from.
3. `splits.py` finds splits as jumps in share counts between consecutive years (tagged ratios first, matched loosely enough to absorb a year of buybacks when the per-share value confirms it; otherwise whole-number ratios) and adjusts the years before each jump, since filers restate only recent years.
4. `metrics.py` evaluates [`metrics.toml`](src/screener/data/metrics.toml), where every metric is defined once, then computes growth and consistency stats over 5, 10 (the latest year and the 10 before it), and all years.
5. `store.py` keeps everything in one DuckDB file; `screen.py` compiles a screen file to one SQL query, with `percent_rank()` for the composite score.
6. `prices.py` gets quotes and daily closes through one small provider interface (an OpenBB adapter, or recorded files) and caches them in `screener.prices.duckdb`.
7. `valuation.py` turns a quote and the latest fiscal year's per-share values into live ratios (also `live.*` screen columns), and prices each fiscal year at the close on the day its numbers were first filed for historical ratios.
   A company whose filings and price are in different currencies, or that files a 20-F (depositary receipts), gets a flag instead of ratios.
8. `kelly.py` shrinks the covariance of daily log returns (Ledoit–Wolf) and solves `max wᵀ(μ − r) − (1 / 2c) wᵀΣw` long only, with total and per-holding caps; `portfolio.py` reads the portfolio file and suggests each holding's expected return (FCF or earnings yield plus capped growth, or the mean price return).

A screen file is TOML; see [`screens/compounders.toml`](screens/compounders.toml).
Columns are `metric.stat`, such as `bvps.cagr`, `roe.avg`, or `debt_to_equity.latest`.
Live ratios are columns too, such as `live.pb` or `live.fcf_yield`; they are empty for companies without a cached quote.
The composite score is the weighted average of each chosen column's percentile rank (0 to 100) among the companies left after filtering; a company missing a column is ranked on the others, and `score_coverage` shows how much of the weight had data.

A portfolio file is TOML too:

```toml
name = "Core"
value = 100000.0

[kelly]
fraction = 0.5        # half Kelly
risk_free = 0.04
max_total = 1.0       # at most 100% invested; above 1 is leverage
max_weight = 0.25     # optional cap per holding
lookback_years = 5.0  # covariance of daily log returns
growth_cap = 0.10     # cap on growth in suggested returns
sensitivity = 0.02    # also show weights with every return this much lower

[[holdings]]
ticker = "KO"
shares = 120.0        # optional, held now: shows current weight and trades
method = "fcf"        # manual (with expected_return), fcf, earnings, or historical
```

## Tests

`uv run pytest` runs on recorded fixtures with no network (see [`tests/fixtures`](tests/fixtures/README.md)), and CI runs it on every pull request that touches this folder.
