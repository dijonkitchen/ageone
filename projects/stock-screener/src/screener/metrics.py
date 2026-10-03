"""Per-share series and ratios from metrics.toml, plus growth and consistency stats."""

from __future__ import annotations

import math
import re
import tomllib
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from typing import Any

import numpy as np
import pandas as pd

from . import splits as split_adjust

STATEMENT_ORDER = {"income_statement": 0, "balance_sheet": 1, "cash_flow": 2, "gap_fill": 3}
WINDOWS = {"5": 5, "10": 10, "all": None}
GROWTH_GROUP = "per_share"
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
FACTOR_INPUTS = ("flow_split_factor", "balance_split_factor")


@dataclass(frozen=True)
class Metric:
    name: str
    label: str
    group: str
    formula: str
    description: str
    higher_is_better: bool = True
    requires_positive: tuple[str, ...] = ()
    concepts: tuple[str, ...] = ()  # line items the formula reaches through its inputs


@dataclass
class Definitions:
    inputs: dict[str, dict[str, Any]]
    metrics: dict[str, Metric]
    splits: dict[str, str]
    raw: dict[str, Any] = field(repr=False, default_factory=dict)


def _names(formula: str) -> list[str]:
    return NAME.findall(formula)


@cache
def definitions() -> Definitions:
    raw = tomllib.loads(resources.files("screener.data").joinpath("metrics.toml").read_text())
    inputs = raw.get("inputs", {})

    def concepts(name: str, seen: frozenset = frozenset()) -> set[str]:
        if name in FACTOR_INPUTS or name in seen:
            return set()
        spec = inputs.get(name)
        if spec is None:
            return {name}
        refs = spec.get("from") or spec.get("sum") or _names(spec.get("formula", ""))
        return set().union(*(concepts(r, seen | {name}) for r in refs)) if refs else set()

    metrics = {}
    for name, spec in raw.get("metrics", {}).items():
        used = set().union(*(concepts(n) for n in _names(spec["formula"])))
        metrics[name] = Metric(
            name=name,
            label=spec["label"],
            group=spec["group"],
            formula=spec["formula"],
            description=spec["description"],
            higher_is_better=spec.get("higher_is_better", True),
            requires_positive=tuple(spec.get("requires_positive", ())),
            concepts=tuple(sorted(used)),
        )
    return Definitions(inputs=inputs, metrics=metrics, splits=raw.get("splits", {}), raw=raw)


def _eval(frame: pd.DataFrame, formula: str) -> pd.Series:
    names = {n: frame[n] if n in frame else pd.Series(np.nan, index=frame.index) for n in _names(formula)}
    with np.errstate(all="ignore"):
        result = pd.eval(formula, local_dict=names, engine="python")
    if not isinstance(result, pd.Series):
        result = pd.Series(result, index=frame.index)
    return result.astype(float).replace([np.inf, -np.inf], np.nan)


def wide(line_items: pd.DataFrame) -> pd.DataFrame:
    """One row per fiscal year, one column per line item (income statement wins duplicates)."""
    if line_items.empty:
        return pd.DataFrame()
    ordered = line_items.assign(_order=line_items["statement"].map(STATEMENT_ORDER).fillna(9))
    ordered = ordered.sort_values(["fiscal_year", "tag", "_order"]).drop_duplicates(["fiscal_year", "tag"])
    return ordered.pivot(index="fiscal_year", columns="tag", values="value").sort_index()


def _missing(frame: pd.DataFrame, defs: Definitions, name: str) -> set[str]:
    """The line items behind an input that has no value in any year, as a reader would name them."""
    if name in frame and frame[name].notna().any():
        return set()
    spec = defs.inputs.get(name)
    if spec is None:
        return set() if name in FACTOR_INPUTS else {name}
    if "from" in spec or "sum" in spec:
        return {" or ".join(spec.get("from") or spec.get("sum"))}
    return set().union(*(_missing(frame, defs, n) for n in _names(spec["formula"])))


@dataclass
class CompanyMetrics:
    values: pd.DataFrame  # fiscal_year, metric, value
    gaps: pd.DataFrame  # metric, years, missing
    splits: list[split_adjust.Split]


def compute(line_items: pd.DataFrame, split_facts: pd.DataFrame | None = None) -> CompanyMetrics:
    defs = definitions()
    frame = wide(line_items)
    if frame.empty:
        return CompanyMetrics(pd.DataFrame(columns=["fiscal_year", "metric", "value"]),
                              pd.DataFrame(columns=["metric", "years", "missing"]), [])
    frame = frame.copy()
    tagged = [] if split_facts is None or split_facts.empty else split_facts["ratio"].tolist()

    def add_input(name: str, spec: dict[str, Any]) -> None:
        if "from" in spec:
            series = pd.Series(np.nan, index=frame.index)
            for source in spec["from"]:
                if source in frame:
                    series = series.fillna(frame[source])
        elif "sum" in spec:
            present = [frame[s] for s in spec["sum"] if s in frame]
            series = pd.concat(present, axis=1).sum(axis=1, min_count=1) if present else pd.Series(np.nan, index=frame.index)
        else:
            series = _eval(frame, spec["formula"])
            if "clip" in spec:
                low, high = spec["clip"]
                series = series.clip(low, high)
        frame[name] = series

    # Inputs the split detection reads come first, then the factors, then the rest.
    split_inputs = {defs.splits.get("flow_shares"), defs.splits.get("balance_shares")}
    for name, spec in defs.inputs.items():
        if name in split_inputs:
            add_input(name, spec)
    found: list[split_adjust.Split] = []
    for factor, key, per_share in (
        ("flow_split_factor", "flow_shares", "diluted_eps"),
        ("balance_split_factor", "balance_shares", None),
    ):
        series_name = defs.splits.get(key)
        shares = frame[series_name] if series_name in frame else pd.Series(dtype=float)
        hints = frame[per_share] if per_share and per_share in frame else None
        detected = split_adjust.detect(shares, tagged, series_name or key, hints)
        found.extend(detected)
        frame[factor] = split_adjust.factors(frame.index, detected)
    for name, spec in defs.inputs.items():
        if name not in split_inputs:
            add_input(name, spec)

    values, gaps = [], []
    for metric in defs.metrics.values():
        series = _eval(frame, metric.formula)
        for required in metric.requires_positive:
            if required in frame:
                series = series.where(frame[required] > 0)
        values.append(pd.DataFrame({"fiscal_year": frame.index, "metric": metric.name, "value": series.values}))
        missing = sorted(set().union(*(_missing(frame, defs, n) for n in _names(metric.formula))))
        gaps.append({"metric": metric.name, "years": int(series.notna().sum()), "missing": ", ".join(missing)})
    out = pd.concat(values, ignore_index=True).dropna(subset=["value"])
    return CompanyMetrics(out.reset_index(drop=True), pd.DataFrame(gaps), found)


# Growth and consistency


def cagr(start: float, end: float, years: int) -> float:
    """Compound annual growth; NaN when either end is at or below zero (no meaningful rate)."""
    if years <= 0 or not (start > 0 and end > 0):
        return math.nan
    return (end / start) ** (1 / years) - 1


def _streak(flags: list[bool]) -> int:
    best = run = 0
    for grew in flags:
        run = run + 1 if grew else 0
        best = max(best, run)
    return best


def series_stats(series: pd.Series, growth: bool) -> dict[str, float]:
    """Stats for one metric's yearly series (indexed by fiscal year) inside a window."""
    series = series.dropna().sort_index()
    stats: dict[str, float] = {"years": float(len(series))}
    if series.empty:
        return stats
    stats["latest"] = float(series.iloc[-1])
    stats["avg"] = float(series.mean())
    stats["median"] = float(series.median())
    if not growth or len(series) < 2:
        return stats
    first_year, last_year = series.index[0], series.index[-1]
    start, end = float(series.iloc[0]), float(series.iloc[-1])
    stats["cagr"] = cagr(start, end, int(last_year - first_year))
    # A marker the screen can filter on: 1 when the endpoints have no CAGR.
    stats["cagr_undefined"] = float(not (start > 0 and end > 0))
    consecutive = [(a, b) for (ya, a), (yb, b) in zip(series.items(), list(series.items())[1:]) if yb - ya == 1]
    grew = [b > a for a, b in consecutive]
    stats["years_grew"] = float(sum(grew))
    stats["growth_streak"] = float(_streak(grew))
    rates = [b / a - 1 for a, b in consecutive if a > 0]
    stats["growth_std"] = float(np.std(rates, ddof=1)) if len(rates) >= 2 else math.nan
    if len(series) >= 3 and (series > 0).all():
        x = np.asarray(series.index, dtype=float)
        y = np.log(series.to_numpy(dtype=float))
        residual = y - np.polyval(np.polyfit(x, y, 1), x)
        total = ((y - y.mean()) ** 2).sum()
        stats["r2"] = float(1 - (residual**2).sum() / total) if total > 0 else 1.0
    else:
        stats["r2"] = math.nan
    return stats


def window_stats(values: pd.DataFrame) -> pd.DataFrame:
    """window, metric, stat, value per window, ending at the latest fiscal year.

    A 10-year window spans 10 years of growth: the latest fiscal year and the 10 before it.
    """
    if values.empty:
        return pd.DataFrame(columns=["window", "metric", "stat", "value"])
    defs = definitions()
    latest = int(values["fiscal_year"].max())
    rows = []
    for window, years in WINDOWS.items():
        in_window = values if years is None else values[values["fiscal_year"] >= latest - years]
        for metric, group in in_window.groupby("metric"):
            spec = defs.metrics.get(metric)
            stats = series_stats(group.set_index("fiscal_year")["value"], growth=bool(spec and spec.group == GROWTH_GROUP))
            rows.extend({"window": window, "metric": metric, "stat": s, "value": v} for s, v in stats.items())
    return pd.DataFrame(rows)
