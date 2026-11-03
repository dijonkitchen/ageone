# Test data

Small cuts of the real source files for the 40 largest Zillow ZIPs in California and New Jersey (20 each), in each source's own layout:

- `Zip_zhvi_sample.csv.gz`: Zillow Home Value Index rows for those ZIPs. Data provided by Zillow.
- `zcta_tract_rel_10.txt`: their rows of the Census 2010 ZCTA to tract relationship file (public domain).
- `tract_outcomes_simple.csv`, `tract_covariates.csv`: those tracts' rows of the Opportunity Atlas files (Census Bureau, public).
- `lea_zcta.csv`: their rows of the NCES EDGE 2024 school district to ZCTA relationship file (public domain).
- `seda_admindist_poolsub_cs_2025.2.csv`: **made up**. The rows have SEDA's columns for the districts above, but the scores are invented from a hash of each district id, because SEDA's data use agreement bars republishing its files in part.
