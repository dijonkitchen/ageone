"""A static HTML report of questions 1 and 2, written under the data folder (git-ignored).

The report holds ZIP-level values derived from SEDA, whose data use agreement bars republishing its
files, so it stays local; the README carries only summary results.
"""

import html
import tomllib
from datetime import date
from pathlib import Path

import pandas as pd

from place_outcomes.analysis import LABELS, Price, Scores

CAVEATS = [
    (
        "Association, not cause: families choose where to live, so these factors describe places, they do not "
        "show what a move would do. For causal estimates of neighborhoods, see Opportunity Insights' work on movers "
        "and the Moving to Opportunity experiment."
    ),
    (
        "Adult outcomes are for children born 1978 to 1983, who grew up in these tracts in the 1980s and 1990s; "
        "today's schools and prices describe the places now."
    ),
    (
        "Tract values are averaged into ZIPs by population, and district values by land area, so a ZIP split "
        "between districts gets a blend of them."
    ),
    "Race and ethnicity composition is left out of every model on purpose; it is never a score for a place.",
    "Zillow's ZIPs are matched to Census ZCTAs by number, which is close but not exact.",
]

SOURCES = [
    ("Data provided by Zillow (Zillow Home Value Index)", "https://www.zillow.com/research/data/"),
    (
        "Stanford Education Data Archive (Version SEDA 2025.2)",
        "https://edopportunity.org/trends/data/downloads/",
    ),
    (
        "Opportunity Atlas, Census Bureau and Opportunity Insights",
        "https://www.census.gov/programs-surveys/ces/data/public-use-data/opportunity-atlas-data-tables.html",
    ),
    (
        "Census 2010 ZCTA to tract relationship file",
        "https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.html",
    ),
    (
        "NCES EDGE geographic relationship files (2024)",
        "https://nces.ed.gov/programs/edge/Geographic/RelationshipFiles",
    ),
]


def _table(df: pd.DataFrame) -> str:
    return df.to_html(index=False, border=0, classes="t", float_format=lambda x: f"{x:,.3f}")


def _scores(s: Scores, title: str) -> str:
    fit = pd.DataFrame(
        {
            "Model": ["Baseline: area income and state", "Linear, all factors", "Gradient boosted, all factors"],
            "Cross-validated R², both states": [s.baseline_r2, s.linear_r2, s.boosted_r2],
            **{f"{state} alone": list(r2) for state, r2 in s.states.items()},
        }
    )
    factors = pd.DataFrame(
        {
            "Factor": [LABELS.get(f, f) for f in s.adds],
            "Standardized coefficient": list(s.coefficients.values()),
            "R² lost without it": list(s.adds.values()),
        }
    ).sort_values("R² lost without it", ascending=False)
    return (
        f"<h2>{html.escape(title)}</h2><p>{s.zips:,} ZIPs in {s.counties} counties; folds hold out whole counties.</p>"
        + _table(fit)
        + _table(factors)
    )


def highlights(path: Path) -> list[str]:
    """ZIPs listed in a local, uncommitted `places.local.toml` as `zips = ["94501", ...]`."""
    if not path.exists():
        return []
    return [str(z) for z in tomllib.loads(path.read_text()).get("zips", [])]


def write(out: Path, q1: Scores, q2: Price, mine: list[str], as_of: date) -> Path:
    premium = pd.DataFrame(
        {
            "State": list(q2.school_premium),
            "Value per SD of school achievement, with controls": [f"{v:+.1%}" for v in q2.school_premium.values()],
            "Without controls": [f"{v:+.1%}" for v in q2.school_premium_raw.values()],
        }
    )
    gaps = q2.residuals.assign(**{"value vs predicted": lambda d: d["gap"].map(lambda g: f"{g:+.0%}")})
    cols = ["zip", "state", "achievement", "kfr", "value vs predicted"]
    parts = [
        f"<h1>Schools, homes, and outcomes by place</h1><p>California and New Jersey ZIPs, home values as of {as_of:%B %Y}.</p>",
        _scores(q1, "Question 1: adult outcomes of children from lower-income families"),
        _scores(q2.scores, "Question 2: home values"),
        "<h3>School premium</h3><p>Controls: area income, density, nearby high-paying jobs, commute, college share, poverty.</p>",
        _table(premium),
        "<h3>Priced below what their factors predict</h3>" + _table(gaps.head(15)[cols]),
        "<h3>Priced above what their factors predict</h3>" + _table(gaps.tail(15).iloc[::-1][cols]),
    ]
    if mine:
        parts.append("<h3>Your places</h3>" + _table(gaps[gaps["zip"].isin(mine)][cols]))
    parts.append("<h2>Caveats</h2><ul>" + "".join(f"<li>{html.escape(c)}</li>" for c in CAVEATS) + "</ul>")
    parts.append(
        "<h2>Sources</h2><ul>" + "".join(f'<li><a href="{u}">{html.escape(n)}</a></li>' for n, u in SOURCES) + "</ul>"
    )
    style = (
        "body{font:15px/1.5 system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem}"
        "table.t{border-collapse:collapse;margin:1rem 0}table.t td,table.t th{padding:.25rem .75rem;"
        "border-bottom:1px solid #ddd;text-align:right}table.t td:first-child,table.t th:first-child{text-align:left}"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        f"<title>Place outcomes</title><style>{style}</style><body>{''.join(parts)}</body></html>\n"
    )
    return out
