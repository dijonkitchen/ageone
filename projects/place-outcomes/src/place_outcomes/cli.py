"""`places`: fetch, build, outcomes, price, bootstrap, step, replay, report."""

import argparse
import sys
from pathlib import Path

import duckdb

from place_outcomes import data, features, forecast, models, report
from place_outcomes.config import Paths, default_paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="places", description=__doc__)
    parser.add_argument("--data", type=Path, default=None, help="where files are cached (default ./data)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch", help="download every source and record its digest")
    sub.add_parser("build", help="build ZIP features and run the data quality checks")
    sub.add_parser("outcomes", help="question 1: spatially cross-validated outcome models")
    sub.add_parser("price", help="question 2: hedonic price model and school price")
    boot = sub.add_parser("bootstrap", help="train and gate the first challenger as of a month")
    boot.add_argument("month", help="YYYY-MM")
    sub.add_parser("step", help="train, gate, and promote as of the newest month")
    rep = sub.add_parser("replay", help="bootstrap on a past month and step monthly to now")
    rep.add_argument("--start", default="2014-01")
    rep.add_argument("--end", default=None)
    rp = sub.add_parser("report", help="write the static HTML report")
    rp.add_argument("--highlight-config", type=Path, default=Path("places.local.json"))
    args = parser.parse_args(argv)

    paths: Paths = Paths(args.data) if args.data else default_paths()
    if args.command == "fetch":
        for name, entry in data.fetch(paths).items():
            print(f"{name}  {entry['fetched']}  {entry['sha256'][:12]}  {entry['url']}")
        return 0
    paths.root.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(paths.warehouse))
    if args.command == "build":
        passed = features.build(con, paths.raw)
        print(f"built; {len(passed)} data quality checks passed")
    elif args.command == "outcomes":
        for label, result in models.outcomes(models.frame(con)).items():
            print(label, {k: round(v, 3) for k, v in result["r2"].items()})
    elif args.command == "price":
        result = models.price(models.frame(con))
        print("log home value", {k: round(v, 3) for k, v in result["r2"].items()})
        print("school price per SD", {k: f"{v:+.1%}" for k, v in result["school_price_per_sd"].items()})
    elif args.command in ("bootstrap", "step"):
        panel = forecast.load_panel(con)
        as_of = panel.months.index(args.month) if args.command == "bootstrap" else len(panel.months) - 1
        print(forecast.step(panel, as_of, forecast.setup(paths), _digests(paths)))
    elif args.command == "replay":
        panel = forecast.load_panel(con)
        print(forecast.replay(con, panel, paths, args.start, args.end).round(4).to_string())
    elif args.command == "report":
        paths.report.write_text(report.build(con, args.highlight_config))
        print(f"wrote {paths.report}")
    return 0


def _digests(paths: Paths) -> dict[str, str]:
    import json

    if not paths.manifest.exists():
        return {}
    return {f"sha256_{k}": v["sha256"][:16] for k, v in json.loads(paths.manifest.read_text()).items()}


if __name__ == "__main__":
    sys.exit(main())
