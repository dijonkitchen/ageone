"""DuckDB SQL: tracts to ZIP codes with the crosswalk, one feature row per ZIP, and checks that stop bad data."""

from pathlib import Path

import duckdb

from place_outcomes.config import BASELINE_COLUMN, BASELINE_FACTOR, FACTORS, LABELS, STATES

MAX_MISSING_SHARE = 0.25  # a factor missing for more ZIPs than this stops the pipeline


class DataQualityError(Exception):
    pass


def _one(con: duckdb.DuckDBPyConnection, sql: str) -> tuple[float, ...]:
    return con.execute(sql).fetchall()[0]


def _run(con: duckdb.DuckDBPyConnection, sql: str, params: dict[str, str] | None = None) -> None:
    con.execute(sql, params).fetchall()


def load(con: duckdb.DuckDBPyConnection, raw: Path) -> None:
    """Read the four sources into `tract`, `crosswalk`, and `zip_value` tables for California and New Jersey."""
    states = ", ".join(f"'{s}'" for s in STATES)
    columns = {**FACTORS, BASELINE_FACTOR: BASELINE_COLUMN}
    select_factors = ", ".join(f"TRY_CAST(c.{src} AS DOUBLE) AS {name}" for name, src in columns.items())
    select_labels = ", ".join(f"TRY_CAST(o.{src} AS DOUBLE) AS {name}" for name, src in LABELS.items())
    key = "lpad(CAST({t}.state AS VARCHAR), 2, '0') || lpad(CAST({t}.county AS VARCHAR), 3, '0') || lpad(CAST({t}.tract AS VARCHAR), 6, '0')"
    _run(
        con,
        f"""
        CREATE OR REPLACE TABLE tract AS
        SELECT {key.format(t="c")} AS geoid, lpad(CAST(c.state AS VARCHAR), 2, '0') AS state_fips,
               lpad(CAST(c.state AS VARCHAR), 2, '0') || lpad(CAST(c.county AS VARCHAR), 3, '0') AS county_fips,
               {select_factors}, {select_labels}
        FROM read_csv($cov, all_varchar = true) c
        LEFT JOIN read_csv($out, all_varchar = true) o
          ON o.state = c.state AND o.county = c.county AND o.tract = c.tract
        WHERE lpad(CAST(c.state AS VARCHAR), 2, '0') IN ({states})
        """,
        {"cov": str(raw / "atlas_covariates.csv"), "out": str(raw / "atlas_outcomes.csv")},
    )
    # Residential weights: a tract's share of the ZIP's residents (2010 Census block counts), among kept tracts.
    _run(
        con,
        f"""
        CREATE OR REPLACE TABLE crosswalk AS
        SELECT zip, geoid, poppt, poppt / sum(poppt) OVER (PARTITION BY zip) AS weight
        FROM (SELECT ZCTA5 AS zip, GEOID AS geoid, TRY_CAST(POPPT AS DOUBLE) AS poppt
              FROM read_csv($rel, all_varchar = true, delim = ',', header = true)
              WHERE left(GEOID, 2) IN ({states}))
        WHERE poppt > 0
        """,
        {"rel": str(raw / "zcta_tract_rel_10.txt")},
    )
    _run(
        con,
        """
        CREATE OR REPLACE TABLE zip_value AS
        WITH wide AS (SELECT * FROM read_csv($zhvi, all_varchar = true) WHERE State IN ('CA', 'NJ'))
        SELECT lpad(RegionName, 5, '0') AS zip, State AS state, CountyName AS county_name,
               CAST(month AS DATE) AS month, TRY_CAST(value AS DOUBLE) AS value
        FROM (UNPIVOT wide ON COLUMNS(* EXCLUDE (RegionID, SizeRank, RegionName, RegionType, StateName, State, City, Metro, CountyName))
              INTO NAME month VALUE value)
        WHERE value IS NOT NULL AND value <> ''
        """,
        {"zhvi": str(raw / "zhvi.csv")},
    )


def build_features(con: duckdb.DuckDBPyConnection) -> int:
    """One row per ZIP with every factor and label as a residential-weighted tract average, the main county,
    and `n_tracts`, how many source areas fed each value."""
    names = [*FACTORS, BASELINE_FACTOR, *LABELS]
    averages = ", ".join(
        f"sum(x.weight * t.{n}) FILTER (WHERE t.{n} IS NOT NULL) / sum(x.weight) FILTER (WHERE t.{n} IS NOT NULL) AS {n}"
        for n in names
    )
    _run(
        con,
        f"""
        CREATE OR REPLACE TABLE zip_features AS
        SELECT x.zip, any_value(t.state_fips) AS state_fips,
               -- the county holding most of the ZIP's residents, used to keep neighbors in the same CV fold
               arg_max(t.county_fips, x.weight) AS county_fips, count(*) AS n_tracts, {averages}
        FROM crosswalk x JOIN tract t USING (geoid)
        GROUP BY x.zip
        """,
    )
    row = _one(con, "SELECT count(*) FROM zip_features")
    return int(row[0])


def check(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Raise `DataQualityError` listing every failed check; return the names of the checks that passed."""
    problems: list[str] = []
    passed: list[str] = []

    def record(name: str, ok: bool, detail: str) -> None:
        if ok:
            passed.append(name)
        else:
            problems.append(f"{name}: {detail}")

    row = _one(
        con, "SELECT count(*) FROM (SELECT zip, sum(weight) AS s FROM crosswalk GROUP BY zip) WHERE abs(s - 1) > 1e-9"
    )
    record("crosswalk weights sum to 1", row[0] == 0, f"{row[0]} ZIPs do not")
    total = _one(con, "SELECT count(*) FROM zip_features")
    record("ZIPs exist", total[0] > 0, "no ZIP has features")
    for name in [*FACTORS, *LABELS]:
        missing = _one(con, f"SELECT avg(CASE WHEN {name} IS NULL THEN 1 ELSE 0 END) FROM zip_features")
        share = float(missing[0] or 0)
        record(f"{name} present", share <= MAX_MISSING_SHARE, f"missing for {share:.0%} of ZIPs")
    bad = _one(
        con,
        "SELECT count(*) FROM zip_features WHERE adult_income_rank NOT BETWEEN 0 AND 1"
        " OR incarceration_rate NOT BETWEEN -0.1 AND 1 OR poverty_share NOT BETWEEN 0 AND 1",
    )
    record("shares and ranks in [0, 1]", bad[0] == 0, f"{bad[0]} ZIPs outside")
    prices = _one(con, "SELECT count(*) FROM zip_value WHERE value <= 1000 OR value > 1e8")
    record("home values plausible", prices[0] == 0, f"{prices[0]} values outside $1,000 to $100,000,000")
    if problems:
        raise DataQualityError("; ".join(problems))
    return passed


def build(con: duckdb.DuckDBPyConnection, raw: Path) -> list[str]:
    load(con, raw)
    build_features(con)
    return check(con)
