"""Report generation.

Covers the two reports needed by §9 build-order stages 3-4. §5's draft-mode
reporting is not implemented yet.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


def crosswalk_report(rosters: pd.DataFrame, crosswalk_unmatched: pd.DataFrame) -> dict:
    """§9 stage 3: "Roster parsing + crosswalk reports. Eyeball the unmatched
    lists." Prints a summary plus the full unmatched list for manual review,
    and enforces the one invariant that actually matters (DATA_DICTIONARY.md
    / §8.2 validate.py): no unmatched name should have a close fuzzy
    neighbour -- that indicates a normalization bug, not a real absence.
    """
    total = len(rosters)
    matched = int(rosters["player_id"].notna().sum())
    standard = rosters[~rosters["two_way"]]
    standard_matched = int(standard["player_id"].notna().sum())
    two_way_count = int(rosters["two_way"].sum())

    near = crosswalk_unmatched[crosswalk_unmatched["fuzzy_suggestion"].notna()]

    summary = {
        "total_roster_entries": total,
        "matched": matched,
        "unmatched": total - matched,
        "standard_contract_matched": standard_matched,
        "standard_contract_total": len(standard),
        "two_way_count": two_way_count,
        "unmatched_with_fuzzy_suggestion": len(near),
    }

    print(f"Roster crosswalk: {matched}/{total} matched "
          f"({standard_matched}/{len(standard)} standard-contract, {two_way_count} two-way)")

    if len(near):
        print("Unmatched entries with a close fuzzy neighbour -- eyeball these, likely a normalization bug:")
        for _, row in near.iterrows():
            print(f"  {row['roster_name']} ({row['team']}) -> {row['fuzzy_suggestion']}")
    else:
        print("  No unmatched name has a close fuzzy neighbour (clean).")

    print(f"\n{len(crosswalk_unmatched)} unmatched roster entries for manual review:")
    cols = ["team", "roster_name", "pos_roster", "two_way", "age_at_season_start", "match"]
    print(crosswalk_unmatched[cols].to_string(index=False))

    if len(near):
        raise AssertionError(
            f"{len(near)} unmatched roster entries have a close fuzzy neighbour -- "
            "extend NAME_ALIASES (src/ingest.py) rather than loosening the matcher."
        )

    return summary


def write_vacated_opportunity(table: pd.DataFrame, path: Path | None = None) -> Path:
    """§3.5: 'Output reports/vacated_opportunity.csv sorted by minutes vacated.'"""
    path = path or (REPORTS_DIR / "vacated_opportunity.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, index=False)
    return path


def write_projections(projected: pd.DataFrame, path: Path | None = None) -> Path:
    """§3 output: 'projected per-game values in all nine categories plus
    FGA, FTA... and projected GP', one row per rostered player."""
    path = path or (REPORTS_DIR / "projections.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    projected.to_csv(path)
    return path


def write_punt_report(punt_reports: dict, path: Path | None = None) -> Path:
    """§4.5: '--punt-report mode that ranks all single-category punts plus
    the common pairs..., and for each shows the top 30 board and how much
    each player's rank moves versus the balanced build.'"""
    path = path or (REPORTS_DIR / "punt_report.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["team", "pos", "VALUE", "rank_punt", "rank_balanced", "rank_move"]
    lines = ["# Punt Report (§4.5)\n"]
    for label, board in punt_reports.items():
        lines.append(f"## {label}\n")
        lines.append("```")
        lines.append(board[cols].round(2).to_string())
        lines.append("```")
        lines.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return path


def write_backtest_report(
    score_actual_full: pd.DataFrame,
    score_actual_pool: pd.DataFrame,
    score_proxy_full: pd.DataFrame,
    score_proxy_pool: pd.DataFrame,
    grid_comparison: pd.DataFrame | None,
    misses_by_category: dict,
    n_players: int,
    n_pool: int,
    path: Path | None = None,
) -> Path:
    """§8.4 backtest report: per-category MAE/correlation under both
    minutes scenarios, each reported over the full backtest population and
    restricted to the §4.1 draftable pool; the full regression_k
    grid-search comparison (if run); and the twenty largest misses in each
    direction per category. FG%/FT% are scored as §4.2 volume-weighted
    impact, not the raw percentage -- see src/backtest.py."""
    path = path or (REPORTS_DIR / "backtest.md")
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Backtest Report (§8.4)\n",
        f"Projected 2025-26 from 2023-24/2024-25 only, evaluated against what actually happened. "
        f"{n_players} players in the backtest population, {n_pool} in the §4.1 draftable pool "
        f"(computed from actual 2025-26 outcomes, fixed across both scenarios). "
        f"FG%/FT% are scored as §4.2 volume-weighted impact (FG_IMPACT/FT_IMPACT), not the raw "
        f"percentage -- that's what valuation actually consumes, and it's what makes them "
        f"minutes-sensitive like the counting stats.\n",
        "## Scenario A: actual (known) 2025-26 minutes/GP\n",
        "### Full population\n",
        "```", score_actual_full.round(4).to_string(), "```", "",
        "### Restricted to the §4.1 draftable pool\n",
        "```", score_actual_pool.round(4).to_string(), "```", "",
        "## Scenario B: previous-season minutes/GP as a naive proxy\n",
        "### Full population\n",
        "```", score_proxy_full.round(4).to_string(), "```", "",
        "### Restricted to the §4.1 draftable pool\n",
        "```", score_proxy_pool.round(4).to_string(), "```", "",
    ]
    if grid_comparison is not None:
        lines += [
            "## regression_k grid search (§3.3 tuning)\n",
            "```", grid_comparison.round(4).to_string(), "```", "",
        ]
    lines.append("## Twenty largest misses in each direction, per category (full population)\n")
    for cat, misses in misses_by_category.items():
        lines.append(f"### {cat}\n")
        lines.append("```")
        lines.append(misses.round(2).to_string())
        lines.append("```")
        lines.append("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return path
