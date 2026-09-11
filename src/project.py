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
    usage of players no longer on it. "The single strongest quantitative
    signal for breakouts... fully derivable from data already in hand."
    Matches the schema shipped in data/canonical/vacated_opportunity.csv
    (§1), including usg_wtd_vacated / usg_minutes_vacated -- per
    DATA_DICTIONARY.md, usg_minutes_vacated (usage x minutes freed) is the
    metric §3.5's prose actually calls for; pts_p100_wtd_vacated and
    mp_vacated are retained for cross-checking."""
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
        # Usage-weighted vacancy (DATA_DICTIONARY.md: "the metric spec §3.5 calls for").
        # Minutes tell you playing time freed; usage tells you shots and possessions
        # freed, which ranks teams differently -- a team can vacate many low-usage
        # minutes or fewer high-usage ones.
        usg_mp_gone = (gone["usg_pct"].fillna(0) * gone["mp"].fillna(0)).sum()
        wtd_usg = usg_mp_gone / mp_gone if mp_gone else 0.0

        records.append(
            {
                "team": team,
                "mp_2526_single_team": mp_total,
                "mp_vacated": mp_gone,
                "pct_vacated": round(100 * mp_gone / mp_total, 1) if mp_total else 0.0,
                "pts_p100_wtd_vacated": round(wtd_pts, 1),
                "usg_wtd_vacated": round(wtd_usg, 1),
                "usg_minutes_vacated": round(usg_mp_gone / 100, 0),
                "n_departed": int(len(gone)),
            }
        )

    return pd.DataFrame(records).sort_values("mp_vacated", ascending=False).reset_index(drop=True)


# -------------------------------------------------- §3.1-3.3, 3.6-3.7 projection assembly

# Category label (matching config/league.yaml's regression_k keys) -> the
# player_seasons.csv column it blends from. player_seasons.csv (not
# player_team_seasons.csv) is used here per §1: "player-level projection
# work" uses the season-combined file, not the team-split one.
CATEGORY_COLUMNS = {
    "PTS": "pts_p100",
    "REB": "trb_p100",
    "AST": "ast_p100",
    "STL": "stl_p100",
    "BLK": "blk_p100",
    "3PM": "fg3_p100",
    "TOV": "tov_p100",
    "FG": "fg_pct",
    "FT": "ft_pct",
}
# FGA/FTA aren't in the spec's §3.3 K table -- they reuse FG's/FT's K, since
# attempt volume and shooting percentage share the same shot-selection/role
# signal and reliability timeline. Spec doesn't specify this; documented as
# an interpretive choice. Needed per §3 "Output": "plus FGA, FTA (needed
# for percentage impact)".
VOLUME_COLUMNS = {"FGA": ("fga_p100", "FG"), "FTA": ("fta_p100", "FT")}

_ALL_COLS = list(dict.fromkeys(list(CATEGORY_COLUMNS.values()) + [c for c, _ in VOLUME_COLUMNS.values()]))
# _LABEL_BY_COL: which K constant / age curve a column uses (FGA and fg_pct
# share "FG" here deliberately -- see VOLUME_COLUMNS docstring).
_LABEL_BY_COL = {col: label for label, col in CATEGORY_COLUMNS.items()}
_LABEL_BY_COL.update({col: k_label for col, k_label in VOLUME_COLUMNS.values()})
# _OUTPUT_LABEL_BY_COL: the assembled DataFrame's column name. Deliberately
# distinct from _LABEL_BY_COL for fga_p100/fta_p100 -- FG/FT are the rate
# fields (fg_pct/ft_pct), FGA/FTA the volumes; conflating them would
# silently overwrite one with the other.
_OUTPUT_LABEL_BY_COL = {col: label for label, col in CATEGORY_COLUMNS.items()}
_OUTPUT_LABEL_BY_COL["fg_pct"] = "FG_PCT"
_OUTPUT_LABEL_BY_COL["ft_pct"] = "FT_PCT"
_OUTPUT_LABEL_BY_COL.update({col: vol_label for vol_label, (col, _) in VOLUME_COLUMNS.items()})
RATE_OUTPUT_LABELS = {"FG_PCT", "FT_PCT"}


def load_league_config() -> dict:
    with open(CONFIG_DIR / "league.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _blend_column(rows: pd.DataFrame, col: str, season_weights: dict[str, float]) -> float | None:
    """One player's rows (their available seasons) -> blended rate for one
    column. §3.2: weight = season_weight * minutes played that season.
    Seasons where the column is null (e.g. ft_pct with 0 FTA) are excluded
    from THIS column's blend only -- other columns from that same season
    still contribute. Renormalization falls out automatically: it's a
    weighted average, not weights forced to sum to 1 up front."""
    num = den = 0.0
    for _, row in rows.iterrows():
        val = row[col]
        mp = row["mp"] or 0
        if pd.isna(val) or mp <= 0:
            continue
        w = season_weights.get(row["season"], 0.0) * mp
        num += w * val
        den += w
    return (num / den) if den else None


def blend_seasons(
    player_seasons: pd.DataFrame,
    player_ids: list[str],
    season_weights: dict[str, float],
) -> pd.DataFrame:
    """§3.2 multi-season blend for every category/volume column, for the
    given players, restricted to the seasons present in `season_weights`
    (the backtest passes a 2-season subset to project the held-out season).
    Returns one row per player_id: blended_<col> columns, mp_total (raw
    summed minutes across all seasons present -- a single per-player
    reliability figure used for every category's §3.3 shrinkage, since the
    K constants already encode per-category noisiness), and pos (most
    recent available season's BBRef position)."""
    subset = player_seasons[
        player_seasons["player_id"].isin(player_ids) & player_seasons["season"].isin(season_weights)
    ]

    records = []
    for pid, rows in subset.groupby("player_id"):
        rec = {"player_id": pid}
        for col in _ALL_COLS:
            rec[f"blended_{col}"] = _blend_column(rows, col, season_weights)
        rec["mp_total"] = rows["mp"].fillna(0).sum()
        rec["pos"] = rows.sort_values("season").iloc[-1]["pos"]  # YYYY-YY sorts chronologically
        records.append(rec)
    return pd.DataFrame(records).set_index("player_id")


def positional_baselines(player_seasons: pd.DataFrame, pool_ids: list[str], season: str) -> pd.DataFrame:
    """§3.3: 'Positional baselines computed from the draftable pool (§4.1),
    by Pos, from the most recent season.' Unblended -- a single-season
    average, unlike the multi-season shrinkage target."""
    pool = player_seasons[player_seasons["player_id"].isin(pool_ids) & (player_seasons["season"] == season)]
    return pool.groupby("pos")[_ALL_COLS].mean()


def regress_to_mean(blended: pd.DataFrame, baselines: pd.DataFrame, regression_k: dict[str, float]) -> pd.DataFrame:
    """§3.3: shrunk = (MP_total * observed + K_cat * positional_mean) /
    (MP_total + K_cat). Falls back to the pool-wide mean when a player's
    Pos isn't in the baseline table (position absent from the seed pool)."""
    league_mean = baselines.mean()
    out = blended.copy()
    for col in _ALL_COLS:
        k = regression_k[_LABEL_BY_COL[col]]
        blended_col = f"blended_{col}"
        shrunk_vals = []
        for _, row in out.iterrows():
            pos = row.get("pos")
            baseline = baselines.loc[pos, col] if pos in baselines.index else league_mean[col]
            observed = row[blended_col]
            if pd.isna(observed):
                observed = baseline
            mp_total = row["mp_total"] or 0
            shrunk_vals.append((mp_total * observed + k * baseline) / (mp_total + k))
        out[f"shrunk_{col}"] = shrunk_vals
    return out


# §3.6 age curve -- piecewise-linear multipliers on the shrunk rate, keyed
# on age at the projected season's start. Peak 25-28 on every curve
# (multiplier 1.0). Three curves, per spec's qualitative guidance ("steals
# and blocks decay earlier than assists and free throw rate"): hand-picked,
# not fit to data -- "a first-order correction, not a precision instrument".
AGE_CURVE_EARLY_DECAY = [(19, 0.88), (22, 0.96), (25, 1.00), (28, 1.00), (31, 0.90), (34, 0.75), (38, 0.55)]
AGE_CURVE_DEFAULT = [(19, 0.90), (22, 0.97), (25, 1.00), (28, 1.00), (32, 0.95), (36, 0.85), (40, 0.70)]
AGE_CURVE_LATE_DECAY = [(19, 0.85), (22, 0.95), (25, 1.00), (28, 1.00), (33, 0.97), (37, 0.90), (40, 0.80)]

AGE_CURVE_BY_LABEL = {
    "STL": AGE_CURVE_EARLY_DECAY,
    "BLK": AGE_CURVE_EARLY_DECAY,
    "AST": AGE_CURVE_LATE_DECAY,
    "FT": AGE_CURVE_LATE_DECAY,
    "PTS": AGE_CURVE_DEFAULT,
    "REB": AGE_CURVE_DEFAULT,
    "3PM": AGE_CURVE_DEFAULT,
    "TOV": AGE_CURVE_DEFAULT,
    "FG": AGE_CURVE_DEFAULT,
}


def _interp_curve(curve: list[tuple[float, float]], age: float) -> float:
    if age <= curve[0][0]:
        return curve[0][1]
    if age >= curve[-1][0]:
        return curve[-1][1]
    for (a0, m0), (a1, m1) in zip(curve, curve[1:]):
        if a0 <= age <= a1:
            return m0 if a1 == a0 else m0 + (age - a0) / (a1 - a0) * (m1 - m0)
    return curve[-1][1]


def apply_age_curve(shrunk: pd.DataFrame, ages: pd.Series) -> pd.DataFrame:
    """§3.6: apply the age curve to the shrunk per-100 rates."""
    out = shrunk.copy()
    for col in _ALL_COLS:
        curve = AGE_CURVE_BY_LABEL[_LABEL_BY_COL[col]]
        shrunk_col = f"shrunk_{col}"
        adj = []
        for pid, val in out[shrunk_col].items():
            age = ages.get(pid)
            mult = _interp_curve(curve, age) if age is not None and not pd.isna(age) else 1.0
            adj.append(val * mult if not pd.isna(val) else val)
        out[f"aged_{col}"] = adj
    return out


# ------------------------------------------- §3.5 minutes / games-played configs


def generate_minutes_config(rosters: pd.DataFrame, player_seasons: pd.DataFrame, path: Path | None = None) -> Path:
    """§3.5: 'Generate config/minutes.yaml, one entry per rostered player,
    pre-populated with last season's MPG as a starting point and flagged
    estimated: true. The user edits it.' This session was explicitly told
    not to fill it in -- every player stays estimated: true."""
    path = path or (CONFIG_DIR / "minutes.yaml")
    matched = rosters.dropna(subset=["player_id"]).drop_duplicates("player_id")
    most_recent_mpg = (
        player_seasons.sort_values("season").drop_duplicates("player_id", keep="last").set_index("player_id")["mpg"]
    )
    entries = {}
    for pid in matched["player_id"]:
        mpg = most_recent_mpg.get(pid)
        # Zero NBA history (rookie / international signee, no matched
        # season at all) -- flat bench-level placeholder so pool selection
        # doesn't crash. Still flagged estimated; this is exactly the kind
        # of entry a human is supposed to correct.
        entries[pid] = round(float(mpg), 1) if pd.notna(mpg) else 15.0
    doc = {"minutes": {pid: {"mpg": mpg, "estimated": True} for pid, mpg in entries.items()}}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(doc, fh, sort_keys=True)
    return path


def generate_games_played_config(rosters: pd.DataFrame, path: Path | None = None, default_gp: int = 82) -> Path:
    """§3.5: same pattern as minutes -- default 82, user edits down."""
    path = path or (CONFIG_DIR / "games_played.yaml")
    matched = rosters.dropna(subset=["player_id"]).drop_duplicates("player_id")
    doc = {"games_played": {pid: {"gp": default_gp, "estimated": True} for pid in matched["player_id"]}}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(doc, fh, sort_keys=True)
    return path


def load_minutes_config(path: Path | None = None) -> dict[str, dict]:
    path = path or (CONFIG_DIR / "minutes.yaml")
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    return doc.get("minutes", {})


def load_games_played_config(path: Path | None = None) -> dict[str, dict]:
    path = path or (CONFIG_DIR / "games_played.yaml")
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    return doc.get("games_played", {})


def minutes_sanity_check(rosters: pd.DataFrame, minutes_cfg: dict, games_played_cfg: dict) -> pd.DataFrame:
    """§3.5: 'projected minutes per team must total 240 x 82 +/- 3%. Report
    teams that violate it rather than silently rescaling.'"""
    matched = rosters.dropna(subset=["player_id"]).drop_duplicates("player_id").copy()
    matched["proj_minutes"] = matched["player_id"].map(
        lambda pid: minutes_cfg.get(pid, {}).get("mpg", 0) * games_played_cfg.get(pid, {}).get("gp", 0)
    )
    totals = matched.groupby("team")["proj_minutes"].sum()
    target = 240 * 82
    report = pd.DataFrame({"team": totals.index, "total_projected_minutes": totals.values})
    report["target"] = target
    report["pct_of_target"] = round(100 * report["total_projected_minutes"] / target, 1)
    report["within_3pct"] = report["total_projected_minutes"].between(target * 0.97, target * 1.03)
    return report.sort_values("pct_of_target").reset_index(drop=True)


# ------------------------------------------------------------- §3.7 assembly


def assemble_projection(
    aged: pd.DataFrame,
    minutes_cfg: dict,
    games_played_cfg: dict,
    pace: pd.Series,
    rosters: pd.DataFrame,
) -> pd.DataFrame:
    """§3.7: per_game_stat = shrunk_per100_rate/100 * pace * (mpg/48);
    season_total = per_game_stat * GP. FG%/FT% are already rates -- they
    pass through the aged value unscaled."""
    team_by_player = rosters.dropna(subset=["player_id"]).drop_duplicates("player_id").set_index("player_id")["team"]
    league_avg_pace = pace.mean()

    rows = []
    for pid, row in aged.iterrows():
        team = team_by_player.get(pid)
        team_pace = pace.get(team, league_avg_pace) if team is not None else league_avg_pace
        mpg_info = minutes_cfg.get(pid, {"mpg": 15.0, "estimated": True})
        gp_info = games_played_cfg.get(pid, {"gp": 82, "estimated": True})
        mpg, gp = mpg_info["mpg"], gp_info["gp"]

        out = {
            "player_id": pid,
            "team": team,
            "pos": row.get("pos"),
            "mpg": mpg,
            "gp": gp,
            "minutes_estimated": mpg_info["estimated"],
            "gp_estimated": gp_info["estimated"],
        }
        for col in _ALL_COLS:
            out_label = _OUTPUT_LABEL_BY_COL[col]
            aged_val = row[f"aged_{col}"]
            if out_label in RATE_OUTPUT_LABELS:
                out[out_label] = aged_val
            else:
                per_game = (aged_val / 100) * team_pace * (mpg / 48) if not pd.isna(aged_val) else None
                out[out_label] = per_game
                out[f"{out_label}_season"] = per_game * gp if per_game is not None else None
        rows.append(out)
    return pd.DataFrame(rows).set_index("player_id")


def project_players(data: dict, config: dict | None = None, minutes_cfg=None, games_played_cfg=None) -> pd.DataFrame:
    """Orchestrates §3.2 -> §3.3 -> §3.6 -> §3.7 for every matched rostered
    player. A player with zero player_seasons history (no 2023-26 NBA
    season at all) can't be projected from this historical-blend-only
    method and is excluded -- see §10 (ADP/rookie modeling explicitly out
    of scope)."""
    config = config or load_league_config()
    season_weights = config["projection"]["season_weights"]
    regression_k = config["projection"]["regression_k"]

    rosters = data["rosters"]
    player_seasons = data["player_seasons"]
    matched = rosters.dropna(subset=["player_id"]).drop_duplicates("player_id")
    player_ids = sorted(set(player_seasons["player_id"]) & set(matched["player_id"]))

    blended = blend_seasons(player_seasons, player_ids, season_weights)

    minutes_cfg = minutes_cfg if minutes_cfg is not None else load_minutes_config()
    seed_mpg = {pid: minutes_cfg.get(pid, {}).get("mpg", 15.0) for pid in player_ids}
    seed_pool_ids = sorted(seed_mpg, key=lambda p: -seed_mpg[p])[:150]

    most_recent_season = max(season_weights, key=lambda s: s)  # YYYY-YY sorts chronologically
    baselines = positional_baselines(player_seasons, seed_pool_ids, most_recent_season)
    shrunk = regress_to_mean(blended, baselines, regression_k)

    ages = matched.set_index("player_id")["age_at_season_start"]
    aged = apply_age_curve(shrunk, ages)

    games_played_cfg = games_played_cfg if games_played_cfg is not None else load_games_played_config()
    pace = project_team_pace_2627(data["team_seasons"])

    return assemble_projection(aged, minutes_cfg, games_played_cfg, pace, rosters)
