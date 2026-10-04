# Test fixtures

- `BLK.companyfacts.json.gz`: BlackRock's real SEC Company Facts response for its current CIK (0002012383, 2023 to 2025), as recorded in OpenBB's own SEC provider tests (Apache 2.0), gzipped.
- `BLK.standardized.csv`: what `screener.standardize` (OpenBB 2.0.0 after our latest-restatement pass, plus our gap fills) makes of it.
  `test_openbb_output_matches_recording` fails when an OpenBB upgrade changes it: check the change against the 10-K, run the spot check, then regenerate with `uv run python tests/record_standardized.py`.
- `../synthetic.py` builds a made-up company with 14 years, two splits (one tagged, one only visible in share counts), and a restatement, with the true values to compare against.

Record more real companies with `screener record-fixture TICKER` (needs SEC access and a configured User-Agent).
