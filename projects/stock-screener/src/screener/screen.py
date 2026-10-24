"""Screens: a plain-text TOML file of filters, sort, and composite weights, compiled to one SQL query."""

from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import tomli_w

from .metrics import GROWTH_GROUP, WINDOWS, definitions
from .valuation import LIVE, LIVE_COLUMNS, QUOTES_VIEW, live_sql, register_quotes

BASE_STATS = ("latest", "avg", "median", "years")
GROWTH_STATS = ("cagr", "cagr_undefined", "years_grew", "growth_streak", "growth_std", "r2")
STAT_LABELS = {
    "latest": "latest", "avg": "average", "median": "median", "years": "years present",
    "cagr": "CAGR", "cagr_undefined": "no CAGR (start or end at or below zero)", "years_grew": "years grew",
    "growth_streak": "longest growth streak", "growth_std": "std. dev. of yearly growth", "r2": "R² of log-linear fit",
}
COMPANY_COLUMNS = ("cik", "ticker", "name", "exchange", "sic", "currency", "last_fiscal_year", "years_of_data")
OPS = (">=", "<=", ">", "<", "=", "!=")


def metric_columns() -> list[str]:
    """Every screenable stat column, named metric.stat."""
    out = []
    for metric in definitions().metrics.values():
        stats = BASE_STATS + (GROWTH_STATS if metric.group == GROWTH_GROUP else ())
        out.extend(f"{metric.name}.{s}" for s in stats)
    return out


def rankable_columns() -> list[str]:
    """Columns a composite score can rank by: metric stats and live price ratios."""
    return [*metric_columns(), *LIVE_COLUMNS]


def all_columns() -> list[str]:
    return [*COMPANY_COLUMNS, *rankable_columns(), "price_flag", "score", "score_coverage"]


def describe(column: str) -> str:
    """Human label and definition for a column, as shown in the UI and exports."""
    metric, _, stat = column.partition(".")
    if metric == "live" and stat in LIVE:
        return f"{LIVE[stat].label} (live): {LIVE[stat].description}"
    spec = definitions().metrics.get(metric)
    if not spec:
        return {"price_flag": "Why live price ratios are left empty: filings and price in different currencies, or depositary receipts.",
                "score": "Composite score: weighted average of percentile ranks (0 to 100) among companies left after filtering.",
                "score_coverage": "Share of composite weight with data for this company.",
                "years_of_data": "Fiscal years with at least one metric."}.get(column, column)
    return f"{spec.label}, {STAT_LABELS.get(stat, stat)}: {spec.description}"


@dataclass
class Filter:
    column: str
    op: str
    value: float


@dataclass
class Weight:
    column: str
    weight: float = 1.0
    higher_is_better: bool | None = None  # None: the metric's own direction


@dataclass
class Screen:
    name: str = "Untitled screen"
    window: str = "10"
    min_years: int = 0
    exchanges: list[str] = field(default_factory=list)
    sic_prefixes: list[str] = field(default_factory=list)
    currencies: list[str] = field(default_factory=list)
    max_fiscal_year_age: int | None = None
    filters: list[Filter] = field(default_factory=list)
    score: list[Weight] = field(default_factory=list)
    sort_by: str = "score"
    descending: bool = True
    columns: list[str] = field(default_factory=list)
    limit: int | None = None

    # File format

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Screen:
        sort = data.get("sort", {})
        screen = cls(
            name=data.get("name", cls.name),
            window=str(data.get("window", "10")),
            min_years=int(data.get("min_years", 0)),
            exchanges=list(data.get("exchanges", [])),
            sic_prefixes=[str(s) for s in data.get("sic_prefixes", [])],
            currencies=list(data.get("currencies", [])),
            max_fiscal_year_age=data.get("max_fiscal_year_age"),
            filters=[Filter(f["column"], f["op"], float(f["value"])) for f in data.get("filters", [])],
            score=[Weight(w["column"], float(w.get("weight", 1.0)), w.get("higher_is_better")) for w in data.get("score", [])],
            sort_by=sort.get("by", "score"),
            descending=bool(sort.get("descending", True)),
            columns=list(data.get("columns", [])),
            limit=data.get("limit"),
        )
        screen.validate()
        return screen

    @classmethod
    def load(cls, path: Path | str) -> Screen:
        return cls.from_dict(tomllib.loads(Path(path).read_text()))

    @classmethod
    def loads(cls, text: str) -> Screen:
        return cls.from_dict(tomllib.loads(text))

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"name": self.name, "window": self.window, "min_years": self.min_years}
        for key in ("exchanges", "sic_prefixes", "currencies", "columns"):
            if getattr(self, key):
                data[key] = getattr(self, key)
        if self.max_fiscal_year_age is not None:
            data["max_fiscal_year_age"] = self.max_fiscal_year_age
        if self.limit is not None:
            data["limit"] = self.limit
        data["sort"] = {"by": self.sort_by, "descending": self.descending}
        if self.filters:
            data["filters"] = [asdict(f) for f in self.filters]
        if self.score:
            data["score"] = [{k: v for k, v in asdict(w).items() if v is not None} for w in self.score]
        return data

    def dumps(self) -> str:
        return tomli_w.dumps(self.to_dict())

    def save(self, path: Path | str) -> None:
        Path(path).write_text(self.dumps())

    def validate(self) -> None:
        known = set(all_columns())
        if self.window not in WINDOWS:
            raise ValueError(f"window must be one of {', '.join(WINDOWS)}, got {self.window!r}")
        for f in self.filters:
            if f.column not in known or f.column in ("score", "score_coverage", "price_flag"):
                raise ValueError(f"unknown filter column {f.column!r}")
            if f.op not in OPS:
                raise ValueError(f"unknown operator {f.op!r}; use one of {' '.join(OPS)}")
        for w in self.score:
            if w.column not in rankable_columns():
                raise ValueError(f"unknown score column {w.column!r}")
        for column in [*self.columns, self.sort_by]:
            if column not in known:
                raise ValueError(f"unknown column {column!r}")

    # Query

    def direction(self, weight: Weight) -> bool:
        if weight.higher_is_better is not None:
            return weight.higher_is_better
        metric, _, stat = weight.column.partition(".")
        if metric == "live":
            return LIVE[stat].higher_is_better
        if stat in ("growth_std", "cagr_undefined"):
            return False
        return definitions().metrics[metric].higher_is_better

    def output_columns(self) -> list[str]:
        chosen = self.columns or [
            *dict.fromkeys([*(f.column for f in self.filters), *(w.column for w in self.score)])
        ]
        lead = ["ticker", "name", "exchange", "currency", "last_fiscal_year", "years_of_data"]
        tail = ["score", "score_coverage"] if self.score else []
        if any(c.startswith("live.") for c in [*chosen, self.sort_by]):
            tail = ["price_flag", *tail]
        return list(dict.fromkeys([*lead, *chosen, *tail, *([self.sort_by] if self.sort_by not in (*lead, "cik") else [])]))

    def sql(self) -> tuple[str, list[Any]]:
        self.validate()
        params: list[Any] = [self.window]
        pivots = ",\n    ".join(
            f"max(value) filter (where metric = '{c.split('.')[0]}' and stat = '{c.split('.')[1]}') as \"{c}\""
            for c in metric_columns()
        )
        where = ["true"]
        if self.min_years:
            where.append("years_of_data >= ?")
            params.append(self.min_years)
        for key, column in (("exchanges", "exchange"), ("currencies", "currency")):
            values = getattr(self, key)
            if values:
                where.append(f"{column} in ({', '.join('?' * len(values))})")
                params.extend(values)
        if self.sic_prefixes:
            where.append("(" + " or ".join("starts_with(coalesce(sic, ''), ?)" for _ in self.sic_prefixes) + ")")
            params.extend(self.sic_prefixes)
        if self.max_fiscal_year_age is not None:
            # Measured against the newest fiscal year in the data, not today, so results are reproducible.
            where.append("last_fiscal_year >= (select max(last_fiscal_year) from companies) - ?")
            params.append(int(self.max_fiscal_year_age))
        for f in self.filters:
            where.append(f'"{f.column}" {f.op} ?')
            params.append(f.value)

        if self.score:
            ranks, weights = [], []
            for w in self.score:
                order = "asc" if self.direction(w) else "desc"
                rank = (f'(case when "{w.column}" is null then null else percent_rank() over '
                        f'(partition by "{w.column}" is null order by "{w.column}" {order}) end)')
                ranks.append(f"coalesce({w.weight!r} * {rank}, 0)")
                weights.append(f"(case when \"{w.column}\" is null then 0 else {w.weight!r} end)")
            total = sum(w.weight for w in self.score)
            score = f"100 * ({' + '.join(ranks)}) / nullif({' + '.join(weights)}, 0)"
            coverage = f"({' + '.join(weights)}) / {total!r}" if total else "null"
        else:
            score, coverage = "null", "null"

        select = ", ".join(f'"{c}"' for c in self.output_columns())
        order = "desc" if self.descending else "asc"
        query = f"""
with {live_sql()}, wide as (
  select cik,
    {pivots}
  from stats where "window" = ?
  group by cik
), years as (
  select cik, count(distinct fiscal_year) as years_of_data from metric_values group by cik
), base as (
  select c.cik, c.ticker, c.name, c.exchange, c.sic, c.currency, c.last_fiscal_year,
         coalesce(y.years_of_data, 0) as years_of_data, w.* exclude (cik), live.* exclude (cik)
  from companies c join wide w using (cik) left join years y using (cik) left join live using (cik)
), filtered as (
  select * from base where {' and '.join(where)}
), ranked as (
  select *, {score} as score, {coverage} as score_coverage from filtered
)
select cik, {select} from ranked
order by "{self.sort_by}" {order} nulls last, ticker, cik"""
        if self.limit:
            query += "\nlimit ?"
            params.append(int(self.limit))
        return query, params

    def run(self, con: duckdb.DuckDBPyConnection, quotes: pd.DataFrame | None = None) -> pd.DataFrame:
        """Run the screen; live.* columns come from `quotes` (ticker, price, currency) and are empty without them."""
        query, params = self.sql()
        register_quotes(con, quotes)
        try:
            return con.execute(query, params).fetchdf()
        finally:
            con.unregister(QUOTES_VIEW)
