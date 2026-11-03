"""Area factors and outcomes by ZIP: the inputs to the outcomes and price questions.

Tract values (Opportunity Atlas outcomes and covariates, on 2010 tracts) are averaged into each ZIP
code tabulation area weighted by the population of the tract's part inside it (Census 2010
relationship file). School district values (SEDA achievement and learning rates, grades 3 to 8) are
averaged weighted by each district's land area inside the ZIP (NCES geographic relationship file),
over the districts SEDA reports, so a high school district with no grade 3 to 8 scores drops out.
Home value is Zillow's ZHVI in the latest month. Zillow's ZIPs are matched to ZCTAs by number.
"""

from pathlib import Path

import duckdb

from place_outcomes.config import (
    LEA_ZCTA_FILE,
    SEDA_FILE,
    STATE_FIPS,
    TRACT_COVARIATES_FILE,
    TRACT_OUTCOMES_FILE,
    ZCTA_TRACT_FILE,
)

# Tract columns averaged into ZIPs: Opportunity Atlas outcome for children of 25th percentile parents,
# and tract traits from its covariates file.
TRACT_COLUMNS = {
    "kfr": "o.kfr_pooled_pooled_p25",  # Adult household income rank (0 to 1).
    "jail": "o.jail_pooled_pooled_p25",  # Share incarcerated on April 1, 2010.
    "med_hhinc": "c.med_hhinc2016",
    "coll": "c.frac_coll_plus2010",
    "poor": "c.poor_share2010",
    "density": "c.popdensity2010",
    "jobs_highpay": "c.jobs_highpay_5mi_2015",
    "commute": "c.mean_commutetime2000",
    "single_parent": "c.singleparent_share2010",
}


def load(con: duckdb.DuckDBPyConnection, raw: Path) -> None:
    """Rebuild the source tables for the two states from the downloaded files."""
    missing = [
        f
        for f in (TRACT_OUTCOMES_FILE, TRACT_COVARIATES_FILE, ZCTA_TRACT_FILE, LEA_ZCTA_FILE)
        if not (raw / f).exists()
    ]
    if missing:
        raise SystemExit(f"missing {', '.join(missing)} in {raw}: run `places fetch`")
    fips = list(STATE_FIPS.values())
    cols = ", ".join(f"TRY_CAST({expr} AS DOUBLE) AS {name}" for name, expr in TRACT_COLUMNS.items())
    con.execute(
        f"""
        CREATE OR REPLACE TABLE tracts AS
        SELECT lpad(o.state::VARCHAR, 2, '0') || lpad(o.county::VARCHAR, 3, '0') || lpad(o.tract::VARCHAR, 6, '0')
               AS tract, {cols}
        FROM read_csv($outcomes, all_varchar = true) o
        JOIN read_csv($covariates, all_varchar = true) c USING (state, county, tract)
        WHERE list_contains($fips, lpad(o.state, 2, '0'))
        """,
        {"outcomes": str(raw / TRACT_OUTCOMES_FILE), "covariates": str(raw / TRACT_COVARIATES_FILE), "fips": fips},
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE zcta_tract AS
        SELECT ZCTA5 AS zip, GEOID AS tract, TRY_CAST(POPPT AS DOUBLE) AS pop
        FROM read_csv($file, all_varchar = true) WHERE list_contains($fips, STATE)
        """,
        {"file": str(raw / ZCTA_TRACT_FILE), "fips": fips},
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE lea_zcta AS
        SELECT LEAID AS leaid, ZCTA5CE20 AS zip, TRY_CAST(LANDAREA AS DOUBLE) AS land
        FROM read_csv($file, all_varchar = true) WHERE list_contains($fips, left(LEAID, 2))
        """,
        {"file": str(raw / LEA_ZCTA_FILE), "fips": fips},
    )
    seda = raw / SEDA_FILE
    if not seda.exists():  # Questions 1 and 2 then run without school measures.
        con.execute("CREATE OR REPLACE TABLE seda (leaid VARCHAR, achievement DOUBLE, learning DOUBLE)")
        return
    con.execute(
        """
        CREATE OR REPLACE TABLE seda AS
        -- All students, cohort scale, averaged over math and reading: achievement is the grade 3 to 8
        -- average in grade levels against the national average, learning the growth per grade.
        SELECT lpad(sedaadmin, 7, '0') AS leaid,
               (TRY_CAST(cs_mn_avg_mth_ol AS DOUBLE) + TRY_CAST(cs_mn_avg_rla_ol AS DOUBLE)) / 2 AS achievement,
               (TRY_CAST(cs_mn_lrn_mth_ol AS DOUBLE) + TRY_CAST(cs_mn_lrn_rla_ol AS DOUBLE)) / 2 AS learning
        FROM read_csv($file, all_varchar = true)
        WHERE subgroup = 'all' AND list_contains($states, stateabb)
        """,
        {"file": str(seda), "states": list(STATE_FIPS)},
    )


def build(con: duckdb.DuckDBPyConnection) -> int:
    """Rebuild `zip_factors`, one row per ZIP with a Zillow value in the two states."""
    avg = ", ".join(
        f"sum(t.pop * x.{c}) FILTER (WHERE x.{c} IS NOT NULL) / "
        f"nullif(sum(t.pop) FILTER (WHERE x.{c} IS NOT NULL), 0) AS {c}"
        for c in TRACT_COLUMNS
    )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE zip_factors AS
        WITH tract_avg AS (
            SELECT t.zip, sum(t.pop) AS pop, arg_max(left(t.tract, 5), t.pop) AS county, {avg}
            FROM zcta_tract t JOIN tracts x USING (tract) WHERE t.pop > 0 GROUP BY t.zip
        ),
        school_avg AS (
            SELECT l.zip, sum(l.land * s.achievement) / sum(l.land) AS achievement,
                   sum(l.land * s.learning) / sum(l.land) AS learning, count(*) AS districts
            FROM lea_zcta l JOIN seda s USING (leaid)
            WHERE l.land > 0 AND s.achievement IS NOT NULL AND s.learning IS NOT NULL GROUP BY l.zip
        ),
        latest AS (SELECT max(month) AS month FROM zhvi)
        SELECT z.zip, z.state, z.month AS value_month, ln(z.value) AS log_value,
               a.* EXCLUDE (zip), s.* EXCLUDE (zip)
        FROM zhvi z JOIN latest USING (month)
        LEFT JOIN tract_avg a USING (zip) LEFT JOIN school_avg s USING (zip)
        """
    )
    row = con.execute("SELECT count(*) FROM zip_factors").fetchone()
    assert row is not None
    return int(row[0])


def check(con: duckdb.DuckDBPyConnection, max_missing: float = 0.1) -> list[str]:
    """Coverage problems that would make the analyses unrepresentative; empty when coverage is good."""
    problems = []
    for column in ("kfr", "med_hhinc", "achievement"):
        row = con.execute(
            f"SELECT state, avg(({column} IS NULL)::INT) AS missing FROM zip_factors GROUP BY state "
            "HAVING missing > $max ORDER BY state",
            {"max": max_missing},
        ).fetchall()
        problems += [f"{column} missing for {m:.0%} of {s} ZIPs" for s, m in row]
    return problems
