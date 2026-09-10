"""Ingestion layer -- spec §2.

Canonical inputs are already harmonized (see data/canonical/DATA_DICTIONARY.md);
this module's job is limited to what §2 assigns it: read the canonical CSVs,
coerce dtypes correctly, and assert the §8.1-8.2 invariants on load.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_CANONICAL = Path(__file__).resolve().parent.parent / "data" / "canonical"

# §2 rule 2: "A NAME_ALIASES hook. When a new source arrives with different
# name spellings, extend the alias table rather than loosening the matcher."
# Carried over from scripts/harmonize.py (the reference implementation) so
# any future source that needs to match against these canonical files by
# name has one place to extend.
NAME_ALIASES: dict[str, str] = {
    "sviatoslav mykhailiuk": "svi mykhailiuk",
}

_BOOL_COLUMNS_BY_FILE = {
    "player_seasons.csv": {"multi_team"},
    "rosters_2627.csv": {"two_way"},
}


class InvariantError(AssertionError):
    """Raised when a §8 invariant fails on load."""


def _read_csv(name: str) -> pd.DataFrame:
    """Read one canonical CSV. §2 rule 1: empty string -> NaN, never 0 --
    this is pandas' default read_csv behavior, so no extra coercion is
    needed for that part. Columns that are textually True/False are coerced
    to bool explicitly, since a column mixing real bools with blanks can
    come back as object dtype."""
    df = pd.read_csv(DATA_CANONICAL / name)
    for col in _BOOL_COLUMNS_BY_FILE.get(name, ()):
        if col in df.columns and df[col].dtype == object:
            df[col] = df[col].map({"True": True, "False": False})
    return df


def load_teams() -> pd.DataFrame:
    return _read_csv("teams.csv")


def load_player_seasons() -> pd.DataFrame:
    return _read_csv("player_seasons.csv")


def load_player_team_seasons() -> pd.DataFrame:
    return _read_csv("player_team_seasons.csv")


def load_team_seasons() -> pd.DataFrame:
    return _read_csv("team_seasons.csv")


def load_rosters() -> pd.DataFrame:
    return _read_csv("rosters_2627.csv")


def load_crosswalk_unmatched() -> pd.DataFrame:
    return _read_csv("crosswalk_unmatched.csv")


def load_unrostered_players() -> pd.DataFrame:
    return _read_csv("unrostered_players.csv")


def load_vacated_opportunity_canonical() -> pd.DataFrame:
    """The vacated_opportunity.csv shipped as a canonical input (§1). Stage 4
    (§3.5) recomputes this independently in src/project.py -- this loader
    exists so that computation can be regression-checked against a
    known-good reference."""
    return _read_csv("vacated_opportunity.csv")


def load_schedule() -> pd.DataFrame | None:
    """§10: an optional schedule.csv for the deferred playoff-week / slot
    metrics. Absent is fine -- return None rather than erroring."""
    path = DATA_CANONICAL / "schedule.csv"
    return _read_csv("schedule.csv") if path.exists() else None


def assert_ingestion_invariants(player_seasons: pd.DataFrame) -> None:
    """§8.1, adapted to the canonical schema (per-100 and advanced stats
    arrive pre-merged into one file here, so the original per100<->adv
    id-set check collapses into "no duplicate player_id+season rows")."""
    errors: list[str] = []

    counts = player_seasons.groupby("season")["player_id"].nunique()
    for season, expected in {"2023-24": 572, "2024-25": 569, "2025-26": 582}.items():
        got = int(counts.get(season, 0))
        if got != expected:
            errors.append(f"season {season}: expected {expected} players, got {got}")

    dupes = player_seasons.duplicated(subset=["player_id", "season"])
    if dupes.any():
        errors.append(f"{int(dupes.sum())} duplicate (player_id, season) rows")

    n_distinct = player_seasons["player_id"].nunique()
    if n_distinct != 802:
        errors.append(f"expected 802 distinct players, got {n_distinct}")

    by_season = {s: set(g["player_id"]) for s, g in player_seasons.groupby("season")}
    if len(by_season) == 3:
        common_all_three = set.intersection(*by_season.values())
        if len(common_all_three) != 374:
            errors.append(f"expected 374 players in all three seasons, got {len(common_all_three)}")

    zero_fta = player_seasons[player_seasons["fta_p100"] == 0]
    bad_pct = zero_fta[zero_fta["ft_pct"].notna()]
    if len(bad_pct):
        errors.append(
            f"{len(bad_pct)} rows have fta_p100 == 0 but a non-null ft_pct "
            "(fillna(0) upstream would corrupt §4.2's percentage-impact calc)"
        )

    mismatch = player_seasons["team"].isna() != player_seasons["multi_team"]
    if mismatch.any():
        errors.append(f"{int(mismatch.sum())} rows where team-blank disagrees with multi_team")

    if errors:
        raise InvariantError("§8.1 ingestion invariants failed:\n  " + "\n  ".join(errors))


def assert_join_integrity(player_seasons: pd.DataFrame) -> None:
    """§8.2: every player common to two consecutive seasons must show
    exactly +1 age. Zero tolerance -- any failure means the join is broken."""
    errors: list[str] = []
    age = player_seasons.set_index(["player_id", "season"])["age"]

    def check_pair(prev_season: str, next_season: str) -> None:
        prev_ids = set(player_seasons.loc[player_seasons["season"] == prev_season, "player_id"])
        next_ids = set(player_seasons.loc[player_seasons["season"] == next_season, "player_id"])
        common = prev_ids & next_ids
        bad = [pid for pid in common if age[(pid, next_season)] - age[(pid, prev_season)] != 1]
        if bad:
            errors.append(
                f"{prev_season} -> {next_season}: {len(bad)}/{len(common)} common players "
                f"failed the +1 age check: {sorted(bad)[:5]}"
            )

    check_pair("2023-24", "2024-25")
    check_pair("2024-25", "2025-26")

    if errors:
        raise InvariantError("§8.2 join integrity failed:\n  " + "\n  ".join(errors))


def load_canonical(validate: bool = True) -> dict[str, pd.DataFrame]:
    """Load every canonical input. By default asserts §8.1-8.2 on load --
    "nothing else works if this is wrong" (§9 stage 1)."""
    data = {
        "teams": load_teams(),
        "player_seasons": load_player_seasons(),
        "player_team_seasons": load_player_team_seasons(),
        "team_seasons": load_team_seasons(),
        "rosters": load_rosters(),
        "crosswalk_unmatched": load_crosswalk_unmatched(),
        "unrostered_players": load_unrostered_players(),
        "vacated_opportunity_canonical": load_vacated_opportunity_canonical(),
    }
    schedule = load_schedule()
    if schedule is not None:
        data["schedule"] = schedule

    if validate:
        assert_ingestion_invariants(data["player_seasons"])
        assert_join_integrity(data["player_seasons"])

    return data
