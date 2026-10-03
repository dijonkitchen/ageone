# SPEC-0008: Portfolio and Kelly Allocation

## Functional requirements

Extends the [stock screener](SPEC-0007-stock-screener.md) with live prices, price-based ratios, and an interactive portfolio page that sizes positions with the Kelly criterion.

- **Prices**: one small price provider interface, with methods to get a quote and daily price history for a list of tickers, plus adapters behind it.
  - The first adapter goes through OpenBB, so people can use any provider it supports (free or paid) with their own API key; a direct adapter for one provider can replace it without changing anything else.
  - Each quote shows its timestamp, its source, and whether it is real time or delayed; outside market hours it shows the last close.
  - The page refreshes quotes on an interval the user sets (default 60 seconds), within the provider's rate limits, and caches daily history on disk.
- **Live ratios** for each company, from the live price and the latest split-adjusted annual fundamentals from SPEC-0007, each labelled with the fiscal year it uses:
  market cap, P/E, P/B, P/tangible book, P/S, P/FCF, earnings yield, FCF yield, dividend yield, and EV/EBIT (enterprise value = market cap + debt − cash).
  Live ratios are also columns in screens, so a screen can filter or rank by, say, P/B ≤ 1.5 with 10-year BVPS CAGR ≥ 10%.
- **Historical price ratios**: P/E, P/B, P/FCF, and dividend yield at each fiscal year for 10 or more years, priced at the close on the 10-K filing date (when the numbers became public), with the 10-year low, median, and high next to today's value.
- **Portfolio**:
  - Add companies from screen results (selected rows) or by ticker search, and remove them.
  - Each holding shows its live price, live ratios, and key 10-year metrics from SPEC-0007.
  - Optional current shares held per holding, so the page can show current weights and the trades (in shares) that move the portfolio to the suggested weights.
  - A portfolio saves to and loads from one plain-text file (tickers, shares held, return assumptions, and Kelly settings), so it can be reopened and diffed.
- **Kelly allocation**: weights that maximize expected log growth, using the standard approximation `g(w) = r + wᵀ(μ − r) − ½ wᵀΣw`, whose unconstrained solution is `w* = Σ⁻¹(μ − r)`.
  - **Expected returns (μ)**: set per holding, by typing a number or picking a method that suggests one: fundamentals-implied (FCF or earnings yield plus a capped per-share growth rate from SPEC-0007) or historical (mean price return over the lookback).
    The suggestion is shown next to the value used, and the method is saved in the portfolio file.
  - **Covariance (Σ)**: from daily log returns over a lookback the user sets (default 5 years), annualized and shrunk toward a structured target (Ledoit–Wolf), so highly correlated or short-history holdings don't give extreme weights.
  - **Risk-free rate (r)**: set by the user, saved with the portfolio.
  - **Settings**: a Kelly fraction (default ½, since full Kelly is very sensitive to errors in μ), long only, total invested ≤ 100% with the rest in cash (an optional leverage cap above 100%), and an optional maximum weight per holding.
    A fraction `c` solves `max wᵀ(μ − r) − (1 / 2c) wᵀΣw` under the constraints, rather than scaling a constrained full-Kelly answer.
  - **Output**: weight, dollar amount, and whole shares per holding for a portfolio value the user enters; the cash left over; and the portfolio's expected return, volatility, and expected growth rate at full and chosen fraction.
  - **Sensitivity**: how the weights change if every μ is lower by a chosen amount (default 2 percentage points), so people see how much the answer rests on their return guesses.
  - Every input change recomputes the allocation in the page without a reload.

## Non-functional requirements

- API keys live in local config, are never committed, and never reach the browser: the local process calls the provider and the page talks only to it.
- Not financial advice: the portfolio page says the allocation is a mathematical result of the user's own return assumptions, Kelly sizing is aggressive and assumes those assumptions are right, and nothing here is investment advice.
- Correct: tests cover the Kelly solver against the closed-form answers (single asset `f = (μ − r) / σ²`, and unconstrained many assets `Σ⁻¹(μ − r)`), that constrained answers respect every constraint, the fractional Kelly form, a singular or near-singular Σ, the ratio formulas, and filing-date pricing, using recorded price fixtures with no network.
- Deterministic: the same prices, filings, and portfolio file give the same allocation.
- A company whose filings and price are in different currencies, or whose shares trade as depositary receipts, has its price ratios flagged instead of computed wrongly.
- Same stack and environment as [SPEC-0007](SPEC-0007-stock-screener.md).

### Out of scope

- Placing orders, broker connections, tax lots, and transaction costs.
- Short positions, options, and assets other than US-listed common stock.
- Intraday charts, streaming tick data, and backtesting the allocation.

## Definition of done

1. Live quotes, with timestamp, source, and delay shown, come through the provider interface for any ticker in the screener, and refresh on the chosen interval.
2. Live ratios show for each company and can be used in screens, and historical price ratios show 10 or more years for companies with the data.
3. A portfolio can be built from screen results or tickers, saved, reloaded, and allocated by fractional Kelly with the constraints above, giving weights, dollars, whole shares, and the sensitivity view, all updating as inputs change.
4. Tests cover the solver and ratios as above and run in CI.
5. The stack decision record covers the price provider interface and the OpenBB adapter.
