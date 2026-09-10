"""CLI entry point (§7): `python -m src.cli build`.

Currently runs §9 build-order stages 1-4: ingestion + validation, pace,
the roster crosswalk report, and the vacated-opportunity report. Stages
5-9 (projection, valuation, backtest, draft mode, G-score) aren't built yet.
"""

from __future__ import annotations

import argparse
import sys

from src import ingest, project, reports


def build() -> None:
    print("== Stage 1: ingestion + §8.1-8.2 invariants ==")
    data = ingest.load_canonical(validate=True)
    print("  OK -- ingestion invariants and join integrity passed.\n")

    print("== Stage 2: §3.4 pace + §8.3 ==")
    pace_table = project.compute_pace_table(data["player_team_seasons"], data["team_seasons"])
    print(f"  implied league-average pace: {pace_table['pace_implied'].mean():.2f}")
    print(pace_table.sort_values("pace_implied", ascending=False).to_string(index=False))
    print()

    print("== Stage 3: roster parsing + crosswalk report (§2, §2.3) ==")
    reports.crosswalk_report(data["rosters"], data["crosswalk_unmatched"])
    print()

    print("== Stage 4: vacated_opportunity.csv (§3.5) ==")
    vacated = project.compute_vacated_opportunity(data["player_team_seasons"], data["rosters"])
    out_path = reports.write_vacated_opportunity(vacated)
    print(f"  wrote {out_path} ({len(vacated)} teams)")
    print(vacated.to_string(index=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build", help="run the implemented pipeline stages (currently §9 stages 1-4)")
    args = parser.parse_args(argv)

    if args.command == "build":
        build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
