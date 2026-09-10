"""Projection engine -- spec §3.

Only the pieces needed for §9 build-order stages 2 and 4 are implemented so
far: §3.4 (pace) and §3.5 (vacated opportunity). The rest of §3 (rate basis,
season blend, regression, age curve, assembly) is stage 5 and comes later.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

PACE_WARN_LOW, PACE_WARN_HIGH = 95.0, 104.0

# ---------------------------------------------------------------- §3.4 pace


def pace_simple(team_row: pd.Series) -> float:
    """'simple' method: poss_per_game ~= FGA + 0.44*FTA - OREB + TOV.
    Retained for cross-checking only -- runs ~3% high because the source
    lacks opponent columns needed for the full Basketball-Reference
    offensive-rebound correction."""
    return team_row["fga_pg"] + 0.44 * team_row["fta_pg"] - team_row["oreb_pg"] + team_row["tov_pg"]


def pace_implied(team_row: pd.Series, team_player_rows: pd.DataFrame) -> float | None:
    """'implied' method -- solved from the player data itself:

        sum_p [ (pts_p100_p / 100) * P * mp_p / (48 * gp_team) ] = pts_per_game_team

    solved for P. `team_player_rows` must already be restricted to one
    team's rows of player_team_seasons.csv, which carries real per-team
    stints only -- multi-team players are pre-split, so nothing here needs
    excluding (§1: "Any team-level aggregation reads player_team_seasons.csv.
    No exceptions.").
    """
    gp = team_row["gp"]
    denom = (
        (team_player_rows["pts_p100"].fillna(0) / 100)
        * team_player_rows["mp"].fillna(0)
        / (48 * gp)
    ).sum()
    return team_row["pts_pg"] / denom if denom else None


def compute_pace_table(
    player_team_seasons: pd.DataFrame, team_seasons: pd.DataFrame, season: str = "2025-26"
) -> pd.DataFrame:
    """Recompute both pace methods per team from the more-primitive inputs,
    for self-checking against team_seasons.csv's own pace columns (§8.3)."""
    season_rows = player_team_seasons[player_team_seasons["season"] == season]

    records = []
    for _, team_row in team_seasons.iterrows():
        team = team_row["team"]
        team_players = season_rows[season_rows["team"] == team]
        records.append(
            {
                "team": team,
                "pace_simple": pace_simple(team_row),
                "pace_implied": pace_implied(team_row, team_players),
                "minutes_share": team_players["mp"].fillna(0).sum() / (240 * team_row["gp"]),
            }
        )
    table = pd.DataFrame(records)

    league_avg = table["pace_implied"].mean()
    if not (PACE_WARN_LOW <= league_avg <= PACE_WARN_HIGH):
        print(
            f"WARNING: implied league-average pace {league_avg:.1f} is outside "
            f"[{PACE_WARN_LOW}, {PACE_WARN_HIGH}] -- check the input data or team-name mapping."
        )
    return table


def load_pace_overrides() -> dict[str, float]:
    """§3.4: '2026-27 pace is a projection... overridable per-team in config.'"""
    path = CONFIG_DIR / "pace_overrides.yaml"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    return doc.get("pace_overrides") or {}


def project_team_pace_2627(
    team_seasons: pd.DataFrame, overrides: dict[str, float] | None = None
) -> pd.Series:
    """Default each team to its 2025-26 implied pace; apply config overrides
    (coaching changes etc.) on top."""
    if overrides is None:
        overrides = load_pace_overrides()
    projected = team_seasons.set_index("team")["pace_implied"].astype(float).copy()
    for team, value in overrides.items():
        projected.loc[team] = float(value)
    return projected


# ------------------------------------------------------ §3.5 vacated opportunity


def compute_vacated_opportunity(
    player_team_seasons: pd.DataFrame, rosters: pd.DataFrame, prior_season: str = "2025-26"
) -> pd.DataFrame:
    """§3.5: for each 2026-27 roster, sum the prior season's minutes and
    minute-weighted scoring of players no longer on it. "The single
    strongest quantitative signal for breakouts... fully derivable from data
    already in hand." Matches the pts_p100_wtd_vacated schema already shipped
    in data/canonical/vacated_opportunity.csv (§1)."""
    prior = player_team_seasons[player_team_seasons["season"] == prior_season]
    staying_by_team = rosters.dropna(subset=["player_id"]).groupby("team")["player_id"].apply(set)

    records = []
    for team, team_prior in prior.groupby("team"):
        staying = staying_by_team.get(team, set())
        gone = team_prior[~team_prior["player_id"].isin(staying)]

        mp_total = team_prior["mp"].fillna(0).sum()
        mp_gone = gone["mp"].fillna(0).sum()
        wtd_pts = (
            (gone["pts_p100"].fillna(0) * gone["mp"].fillna(0)).sum() / mp_gone if mp_gone else 0.0
        )

        records.append(
            {
                "team": team,
                "mp_2526_single_team": mp_total,
                "mp_vacated": mp_gone,
                "pct_vacated": round(100 * mp_gone / mp_total, 1) if mp_total else 0.0,
                "pts_p100_wtd_vacated": round(wtd_pts, 1),
                "n_departed": int(len(gone)),
            }
        )

    return pd.DataFrame(records).sort_values("mp_vacated", ascending=False).reset_index(drop=True)
