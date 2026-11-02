"""A static HTML page with the tables and charts for all three questions, and the caveats."""

import html
import json
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from place_outcomes import forecast, models
from place_outcomes.config import FACTORS

ATLAS_CAUSAL = "https://opportunityinsights.org/paper/the-opportunity-atlas/"

CAVEATS = [
    (
        "Every outcome and price result is an association. Families choose where to live, so a factor that predicts "
        "outcomes is not shown to cause them. For causal estimates of place effects, read "
        f'<a href="{ATLAS_CAUSAL}">the Opportunity Atlas paper</a> and its follow-ups.'
    ),
    (
        "Outcomes are for children born 1978 to 1983 and grown up by about 2015; the factors describe places around "
        "2010 to 2016. The Atlas tract boundaries and the ZIP crosswalk are from the 2010 Census."
    ),
    (
        "The school measure is the Atlas covariate for average third grade math scores in 2013, a level and not a "
        "growth rate. School growth (SEDA), student wellbeing, walkability, and disaster risk are not in this run."
    ),
    "Race and ethnicity composition never enters a model or a ranking, because of fair housing concerns.",
    (
        "Zillow's smoothed, seasonally adjusted home values are revised over time and are published for each month "
        "around the middle of the next; a replay uses the file as it is today."
    ),
    "Cross-validation holds out whole counties, so scores reflect how well a model travels to unseen counties.",
]


def table(df: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in [df.index.name or "", *df.columns])
    rows = []
    for idx, row in df.iterrows():
        cells = "".join(f"<td>{floatfmt.format(v) if isinstance(v, float) else html.escape(str(v))}</td>" for v in row)
        rows.append(f"<tr><th>{html.escape(str(idx))}</th>{cells}</tr>")
    return f"<table><tr>{head}</tr>{''.join(rows)}</table>"


def bars(values: dict[str, float], width: int = 360) -> str:
    """An inline SVG bar chart of R² values (negative scores draw to the left of zero)."""
    lo, hi = min(0.0, *values.values()), max(0.0, *values.values())
    span = (hi - lo) or 1.0
    zero = (0 - lo) / span * width
    rows = []
    for i, (name, v) in enumerate(values.items()):
        x0, x1 = sorted((zero, (v - lo) / span * width))
        rows.append(
            f'<text x="0" y="{i * 22 + 14}" font-size="12">{html.escape(name)} {v:.2f}</text>'
            f'<rect x="{x0 + 90:.1f}" y="{i * 22 + 3}" width="{max(x1 - x0, 1):.1f}" height="14" fill="#3b6ea5"/>'
        )
    return f'<svg width="{width + 100}" height="{len(values) * 22 + 4}" role="img">{"".join(rows)}</svg>'


def section_model(title: str, result: dict[str, Any]) -> str:
    r2 = result["r2"]
    pdp = pd.DataFrame({f: [f"{x:.2f} → {y:.3f}" for x, y in pts] for f, pts in result["partial_dependence"].items()}).T
    pdp.columns = pd.Index([f"point {i + 1}" for i in range(pdp.shape[1])])
    pdp.index.name = "factor (value → prediction)"
    return (
        f"<h3>{html.escape(title)}</h3><p>{result['n']} ZIPs in {result['counties']} counties. Spatially "
        f"cross-validated R² (whole counties held out). The best model adds "
        f"{result['adds_over_baseline']:+.3f} over the baseline.</p>{bars(r2)}"
        f"<details><summary>Partial dependence of the boosted model</summary>{table(pdp)}</details>"
    )


def extremes(df: pd.DataFrame, highlight: list[str]) -> str:
    out = df.copy()
    out["value"] = [f"${v:,.0f}" for v in (2.718281828459045 ** out["log_value"])]
    out["predicted"] = [f"${v:,.0f}" for v in (2.718281828459045 ** out["oof"])]
    out["residual"] = out["residual"].map(lambda r: f"{r:+.2f}")
    out["zip"] = [f"★ {z}" if z in highlight else z for z in out["zip"]]
    cols = ["zip", "state", "county_name", "value", "predicted", "residual"]
    return table(out[cols].set_index("zip"))


def build(con: duckdb.DuckDBPyConnection, config: Path | None = None) -> str:
    highlight: list[str] = []
    if config and config.exists():  # uncommitted local file naming ZIPs to mark; nothing personal is committed
        highlight = [str(z) for z in json.loads(config.read_text()).get("highlight_zips", [])]
    df = models.frame(con)
    outcome = models.outcomes(df)
    price = models.price(df)
    parts = ["<h1>Schools, homes, and outcomes by place</h1>", "<h2>1. Outcomes</h2>"]
    for label, result in outcome.items():
        parts.append(section_model(f"{label.replace('_', ' ')} (children from low-income families)", result))
    parts.append("<h2>2. Price</h2>")
    parts.append(section_model("log home value", price))
    school = pd.DataFrame({"home value change per +1 SD school score": price["school_price_per_sd"]}).T
    parts.append(f"<p>Within each state, holding the other factors fixed:</p>{table(school.T, '{:+.1%}')}")
    parts.append("<h3>Above their predicted value</h3>" + extremes(price["above_prediction"], highlight))
    parts.append("<h3>Below their predicted value</h3>" + extremes(price["below_prediction"], highlight))
    parts.append("<h2>3. Forecast</h2>")
    has_forecasts = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = 'forecasts'"
    ).fetchall()[0][0]
    if has_forecasts:
        fc: pd.DataFrame = con.execute("SELECT * FROM forecasts").df()
        summary = forecast.summarize(fc)
        summary.index.name = "year of forecast"
        parts.append(f"<p>Mean absolute error of the 12-month change in log home value.</p>{table(summary, '{:.4f}')}")
    else:
        parts.append("<p>No replay has run yet: run <code>places replay</code>.</p>")
    parts.append("<h2>Caveats</h2><ul>" + "".join(f"<li>{c}</li>" for c in CAVEATS) + "</ul>")
    parts.append(
        "<h2>Sources</h2><p>Opportunity Atlas (Opportunity Insights and the U.S. Census Bureau), Census Bureau ZCTA-tract "
        "relationship file, Zillow Home Value Index. Factors: " + ", ".join(FACTORS) + ".</p>"
    )
    style = "body{font:15px/1.5 system-ui;max-width:52rem;margin:2rem auto;padding:0 1rem}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:2px 8px;text-align:right}"
    return f"<!doctype html><meta charset=utf-8><title>Place outcomes</title><style>{style}</style>{''.join(parts)}"
