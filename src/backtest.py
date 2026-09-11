"""Backtest -- spec §8.4.

"Run the pipeline using only 2023-24 and 2024-25 to project 2025-26.
Compare projections to what actually happened." Reuses project.py's
blend/shrink/age-curve/assemble pipeline restricted to the two training
seasons, then reconstructs "actual" 2025-26 values through the identical
§3.7 formula so the comparison isolates rate-projection error rather than
mixing in pace/minutes-formula noise.
"""

from __future__ import annotations

import pandas as pd

from src import project

TARGET_SEASON = "2025-26"
TRAIN_SEASONS = ["2023-24", "2024-25"]
MOST_RECENT_TRAIN_SEASON = "2024-25"

BACKTEST_CATEGORIES = ["PTS", "REB", "AST", "STL", "BLK", "3PM", "TOV", "FG_PCT", "FT_PCT"]

# §3.3 K grid. Log-ish spacing across the plausible range; the spec's own
# guesses (500-1400) sit in the middle of it.
K_GRID = [50, 100, 200, 300, 400, 500, 600, 800, 1000, 1200, 1400, 1600, 2000, 2500, 3000, 4000, 6000]


def _train_season_weights(full_weights: dict[str, float]) -> dict[str, float]:
    """§3.2: drop the held-out season. The remaining weights renormalize
    automatically -- blend_seasons computes a weighted average using only
    the seasons present, not a fixed partition of all three."""
    return {s: w for s, w in full_weights.items() if s in TRAIN_SEASONS}


def backtest_population(player_seasons: pd.DataFrame) -> pd.DataFrame:
    """Players with a real, single-team 2025-26 season (ground truth) and
    at least one training-season row to project from. Multi-team (traded)
    players are excluded: their real 2025-26 line already blends multiple
    teams' pace and player_seasons.csv leaves `team` blank for them (§1.1),
    so there's no single team pace to attribute for reconstructing
    "actual" per-game values."""
    actual = player_seasons[
        (player_seasons["season"] == TARGET_SEASON) & (~player_seasons["multi_team"])
    ].set_index("player_id")
    has_train = set(player_seasons.loc[player_seasons["season"].isin(TRAIN_SEASONS), "player_id"])
    return actual.loc[[pid for pid in actual.index if pid in has_train]]


def actual_table(actual: pd.DataFrame, team_seasons: pd.DataFrame) -> pd.DataFrame:
    """Reconstructs "actual" per-game/season values through the exact same
    §3.7 formula used for projections (aged_<col> = the real, unadjusted
    2025-26 per-100 rate; real mpg/g; real team pace), so any gap between
    this and the projected table is genuinely projection error, not
    formula-reconstruction noise."""
    aged = pd.DataFrame(index=actual.index)
    for col in project._ALL_COLS:
        aged[f"aged_{col}"] = actual[col]
    aged["pos"] = actual["pos"]

    minutes_cfg = {pid: {"mpg": row["mpg"], "estimated": False} for pid, row in actual.iterrows()}
    gp_cfg = {pid: {"gp": row["g"], "estimated": False} for pid, row in actual.iterrows()}
    pace = team_seasons.set_index("team")["pace_implied"]
    rosters = actual.reset_index()[["player_id", "team"]]

    return project.assemble_projection(aged, minutes_cfg, gp_cfg, pace, rosters)


def _baseline_pool_ids(player_seasons: pd.DataFrame, player_ids: list[str], pool_size: int = 150) -> list[str]:
    """Seed pool for positional baselines (§3.3/§4.1): top `pool_size` of
    the backtest population by minutes in the most recent training season,
    mirroring the real pipeline's projected-minutes seed (project.
    project_players) rather than averaging over the full population,
    which would drag baselines toward bench-level play."""
    recent = player_seasons[
        (player_seasons["season"] == MOST_RECENT_TRAIN_SEASON) & player_seasons["player_id"].isin(player_ids)
    ]
    return recent.sort_values("mp", ascending=False).head(pool_size)["player_id"].tolist()


def _proxy_minutes_gp(player_seasons: pd.DataFrame, player_ids: list[str]) -> tuple[dict, dict]:
    """"previous-season minutes as a naive proxy" -- the most recent
    training season's mpg/g per player (2024-25 if present, else
    2023-24)."""
    train = player_seasons[
        player_seasons["season"].isin(TRAIN_SEASONS) & player_seasons["player_id"].isin(player_ids)
    ]
    most_recent = train.sort_values("season").drop_duplicates("player_id", keep="last").set_index("player_id")
    minutes_cfg = {pid: {"mpg": row["mpg"], "estimated": True} for pid, row in most_recent.iterrows()}
    gp_cfg = {pid: {"gp": row["g"], "estimated": True} for pid, row in most_recent.iterrows()}
    return minutes_cfg, gp_cfg


def _projected_table(
    data: dict,
    config: dict,
    player_ids: list[str],
    minutes_cfg: dict,
    gp_cfg: dict,
    actual: pd.DataFrame,
    regression_k: dict | None = None,
) -> pd.DataFrame:
    player_seasons = data["player_seasons"]
    season_weights = _train_season_weights(config["projection"]["season_weights"])
    regression_k = regression_k or config["projection"]["regression_k"]

    blended = project.blend_seasons(player_seasons, player_ids, season_weights)
    baseline_pool = _baseline_pool_ids(player_seasons, player_ids)
    baselines = project.positional_baselines(player_seasons, baseline_pool, MOST_RECENT_TRAIN_SEASON)
    shrunk = project.regress_to_mean(blended, baselines, regression_k)
    ages = actual["age"]  # the real recorded 2025-26 age -- ground truth, not projected
    aged = project.apply_age_curve(shrunk, ages)

    pace = data["team_seasons"].set_index("team")["pace_implied"]
    rosters = actual.reset_index()[["player_id", "team"]]
    return project.assemble_projection(aged, minutes_cfg, gp_cfg, pace, rosters)


def run_backtest(data: dict, config: dict | None = None, regression_k: dict | None = None) -> dict[str, pd.DataFrame]:
    """§8.4: project 2025-26 from 2023-24/2024-25 only, under both minutes
    scenarios, and return tables to compare against what actually
    happened."""
    config = config or project.load_league_config()
    player_seasons = data["player_seasons"]

    actual = backtest_population(player_seasons)
    player_ids = actual.index.tolist()
    actual_tbl = actual_table(actual, data["team_seasons"])

    # Scenario A: "known-actual minutes" -- spec's own name, "optimistic".
    minutes_actual = {pid: {"mpg": row["mpg"], "estimated": False} for pid, row in actual.iterrows()}
    gp_actual = {pid: {"gp": row["g"], "estimated": False} for pid, row in actual.iterrows()}
    proj_actual_minutes = _projected_table(
        data, config, player_ids, minutes_actual, gp_actual, actual, regression_k
    )

    # Scenario B: "previous-season minutes as a naive proxy".
    minutes_proxy, gp_proxy = _proxy_minutes_gp(player_seasons, player_ids)
    proj_proxy_minutes = _projected_table(data, config, player_ids, minutes_proxy, gp_proxy, actual, regression_k)

    return {
        "actual": actual_tbl,
        "projected_actual_minutes": proj_actual_minutes,
        "projected_proxy_minutes": proj_proxy_minutes,
    }


def score_backtest(
    actual_tbl: pd.DataFrame, projected_tbl: pd.DataFrame, categories: list[str] = BACKTEST_CATEGORIES
) -> pd.DataFrame:
    """§8.4: 'Report MAE and correlation per category.'"""
    common = actual_tbl.index.intersection(projected_tbl.index)
    rows = []
    for cat in categories:
        a = actual_tbl.loc[common, cat].astype(float)
        p = projected_tbl.loc[common, cat].astype(float)
        mask = a.notna() & p.notna()
        a, p = a[mask], p[mask]
        rows.append({
            "category": cat,
            "n": int(mask.sum()),
            "mae": (a - p).abs().mean(),
            "corr": a.corr(p),
        })
    return pd.DataFrame(rows).set_index("category")


def largest_misses(
    actual_tbl: pd.DataFrame, projected_tbl: pd.DataFrame, category: str, n: int = 20
) -> pd.DataFrame:
    """§8.4: 'the twenty largest misses in each direction.' Positive error
    = overprojected; negative = underprojected."""
    common = actual_tbl.index.intersection(projected_tbl.index)
    error = (projected_tbl.loc[common, category] - actual_tbl.loc[common, category]).dropna()
    over = error.sort_values(ascending=False).head(n)
    under = error.sort_values().head(n)
    return pd.concat(
        [
            pd.DataFrame({"error": over, "direction": "overprojected"}),
            pd.DataFrame({"error": under, "direction": "underprojected"}),
        ]
    )


def grid_search_regression_k(
    data: dict, config: dict | None = None, k_grid: list[float] = K_GRID
) -> tuple[dict, pd.DataFrame]:
    """§8.4: 'tune regression_k by grid search minimizing backtest error.'

    Each category's shrinkage in §3.3 depends only on that category's own
    observed rate, positional baseline, and K -- categories don't interact.
    So a per-category 1-D grid search is both correct and tractable; no
    need for a combinatorial search over all nine simultaneously.

    Uses the actual-minutes scenario as the tuning target: that isolates
    rate-projection error from minutes-guessing error, and it's the rate
    shrinkage this is meant to tune, not the minutes proxy.
    """
    config = config or project.load_league_config()
    player_seasons = data["player_seasons"]
    actual = backtest_population(player_seasons)
    player_ids = actual.index.tolist()
    actual_tbl = actual_table(actual, data["team_seasons"])

    minutes_actual = {pid: {"mpg": row["mpg"], "estimated": False} for pid, row in actual.iterrows()}
    gp_actual = {pid: {"gp": row["g"], "estimated": False} for pid, row in actual.iterrows()}

    season_weights = _train_season_weights(config["projection"]["season_weights"])
    blended = project.blend_seasons(player_seasons, player_ids, season_weights)
    baseline_pool = _baseline_pool_ids(player_seasons, player_ids)
    baselines = project.positional_baselines(player_seasons, baseline_pool, MOST_RECENT_TRAIN_SEASON)
    ages = actual["age"]
    pace = data["team_seasons"].set_index("team")["pace_implied"]
    rosters = actual.reset_index()[["player_id", "team"]]

    base_k = dict(config["projection"]["regression_k"])
    tuned_k = dict(base_k)
    comparison_rows = []

    for label, col in project.CATEGORY_COLUMNS.items():
        out_label = project._OUTPUT_LABEL_BY_COL[col]  # e.g. "FG" -> "FG_PCT"
        best_k, best_mae, default_mae = base_k[label], None, None
        # Always evaluate the exact current default, even if it isn't one
        # of the grid points, so default_mae/improvement_pct are real.
        grid_for_label = sorted(set(k_grid) | {base_k[label]})
        for k in grid_for_label:
            trial_k = dict(base_k)
            trial_k[label] = k
            shrunk = project.regress_to_mean(blended, baselines, trial_k)
            aged = project.apply_age_curve(shrunk, ages)
            proj = project.assemble_projection(aged, minutes_actual, gp_actual, pace, rosters)
            common = actual_tbl.index.intersection(proj.index)
            a = actual_tbl.loc[common, out_label].astype(float)
            p = proj.loc[common, out_label].astype(float)
            mask = a.notna() & p.notna()
            mae = (a[mask] - p[mask]).abs().mean()
            if k == base_k[label]:
                default_mae = mae
            if best_mae is None or mae < best_mae:
                best_mae, best_k = mae, k
        tuned_k[label] = best_k
        comparison_rows.append(
            {"category": label, "default_k": base_k[label], "default_mae": default_mae,
             "tuned_k": best_k, "tuned_mae": best_mae}
        )

    comparison = pd.DataFrame(comparison_rows).set_index("category")
    comparison["improvement_pct"] = round(
        100 * (comparison["default_mae"] - comparison["tuned_mae"]) / comparison["default_mae"], 1
    )
    return tuned_k, comparison
