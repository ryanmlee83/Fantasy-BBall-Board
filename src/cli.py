"""CLI entry point (§7): `python -m src.cli build`, `... punt-report`, `... backtest`.

Currently runs §9 build-order stages 1-7: ingestion + validation, pace, the
roster crosswalk report, vacated opportunity, projection assembly, Z-score
valuation with punt scenarios, and the §8.4 backtest. Stages 8-9 (draft
mode, G-score) aren't built yet.
"""

from __future__ import annotations

import argparse
import sys

from src import backtest, ingest, project, reports, value


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
    print()

    print("== Stage 5: §3 projection assembly ==")
    config = project.load_league_config()
    minutes_cfg = project.load_minutes_config()
    gp_cfg = project.load_games_played_config()
    n_estimated = sum(1 for v in minutes_cfg.values() if v.get("estimated"))
    print(f"  minutes.yaml: {len(minutes_cfg)} players, {n_estimated} flagged estimated: true")
    sanity = project.minutes_sanity_check(data["rosters"], minutes_cfg, gp_cfg)
    n_ok = int(sanity["within_3pct"].sum())
    print(f"  §3.5 sanity check (240x82 +/-3%): {n_ok}/{len(sanity)} teams within range "
          f"(not rescaled -- see reports/minutes_sanity.csv)")
    sanity_path = project.CONFIG_DIR.parent / "reports" / "minutes_sanity.csv"
    sanity_path.parent.mkdir(parents=True, exist_ok=True)
    sanity.to_csv(sanity_path, index=False)

    projected = project.project_players(data, config, minutes_cfg, gp_cfg)
    proj_path = reports.write_projections(projected)
    print(f"  wrote {proj_path} ({len(projected)} players)")
    print(projected.sort_values("PTS", ascending=False).head(10)[
        ["team", "pos", "mpg", "gp", "PTS", "REB", "AST", "STL", "BLK", "3PM", "TOV", "FG_PCT", "FT_PCT"]
    ].round(2).to_string())


def punt_report_cmd() -> None:
    print("== Stage 6: §4 Z-score valuation + punt scenarios ==")
    data = ingest.load_canonical(validate=False)
    config = project.load_league_config()
    projected = project.project_players(data, config)

    valued, pool_ids, iterations = value.value_players(projected, config["valuation"]["pool_size"])
    print(f"  draftable pool: {len(pool_ids)} players, converged in {iterations} iteration(s)")

    with_impact = value.add_percentage_impact(projected, pool_ids)
    balanced = valued.loc[pool_ids].sort_values("VALUE", ascending=False)
    print("\n  Top 15, balanced build:")
    print(balanced.head(15)[["team", "pos", "PTS", "REB", "AST", "STL", "BLK", "3PM", "TOV",
                              "FG_IMPACT", "FT_IMPACT", "VALUE"]].round(2).to_string())

    punt_reports = value.punt_report(with_impact, pool_ids, top_n=30)
    out_path = reports.write_punt_report(punt_reports)
    print(f"\n  wrote {out_path} ({len(punt_reports)} scenarios)")


def backtest_cmd(run_grid_search: bool) -> None:
    print("== Stage 7: §8.4 backtest ==")
    data = ingest.load_canonical(validate=False)
    config = project.load_league_config()

    regression_k = None
    grid_comparison = None
    if run_grid_search:
        print("  running regression_k grid search (this takes ~1-2 min)...")
        tuned_k, grid_comparison = backtest.grid_search_regression_k(data, config)
        print(grid_comparison.round(4).to_string())
        regression_k = tuned_k

    results = backtest.run_backtest(data, config, regression_k)
    actual, proj_actual, proj_proxy, pool_ids = (
        results["actual"], results["projected_actual_minutes"],
        results["projected_proxy_minutes"], results["pool_ids"],
    )
    print(f"\n  backtest population: {len(actual)} players; draftable pool (§4.1): {len(pool_ids)}\n")

    score_actual_full = backtest.score_backtest(actual, proj_actual)
    score_actual_pool = backtest.score_backtest(actual, proj_actual, restrict_to=pool_ids)
    print("  Scenario A: actual (known) 2025-26 minutes/GP -- full population")
    print(score_actual_full.round(4).to_string())
    print("\n  Scenario A -- restricted to the §4.1 draftable pool")
    print(score_actual_pool.round(4).to_string())

    score_proxy_full = backtest.score_backtest(actual, proj_proxy)
    score_proxy_pool = backtest.score_backtest(actual, proj_proxy, restrict_to=pool_ids)
    print("\n  Scenario B: previous-season minutes/GP as a naive proxy -- full population")
    print(score_proxy_full.round(4).to_string())
    print("\n  Scenario B -- restricted to the §4.1 draftable pool")
    print(score_proxy_pool.round(4).to_string())

    misses_by_category = {
        cat: backtest.largest_misses(actual, proj_actual, cat, n=20) for cat in backtest.BACKTEST_CATEGORIES
    }
    out_path = reports.write_backtest_report(
        score_actual_full, score_actual_pool, score_proxy_full, score_proxy_pool,
        grid_comparison, misses_by_category, len(actual), len(pool_ids),
    )
    print(f"\n  wrote {out_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build", help="run the implemented pipeline stages (currently §9 stages 1-5)")
    sub.add_parser("punt-report", help="§4.5 Z-score valuation + punt scenarios (stage 6)")
    bt = sub.add_parser("backtest", help="§8.4 backtest (stage 7)")
    bt.add_argument("--grid-search", action="store_true", help="also run the regression_k grid search")
    args = parser.parse_args(argv)

    if args.command == "build":
        build()
    elif args.command == "punt-report":
        punt_report_cmd()
    elif args.command == "backtest":
        backtest_cmd(args.grid_search)
    return 0


if __name__ == "__main__":
    sys.exit(main())
