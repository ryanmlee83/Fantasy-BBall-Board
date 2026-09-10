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
