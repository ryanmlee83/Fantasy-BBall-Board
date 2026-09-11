"""Valuation -- spec §4. Z-score only (§4.4 G-score deferred to §9 stage 9)."""

from __future__ import annotations

import pandas as pd

# The nine head-to-head categories (§0), as named in the projection output
# (src/project.py assemble_projection). FG/FT use the volume-weighted
# impact (§4.2) computed by add_percentage_impact, never the raw percentage.
COUNTING_CATEGORIES = ["PTS", "REB", "AST", "STL", "BLK", "3PM", "TOV"]
IMPACT_CATEGORIES = ["FG_IMPACT", "FT_IMPACT"]
ALL_CATEGORIES = COUNTING_CATEGORIES + IMPACT_CATEGORIES
INVERTED_CATEGORIES = {"TOV"}  # §4.3: "Invert the sign on turnovers."

# §4.5: "ranks all single-category punts plus the common pairs (FT%+TO,
# FG%+3PM, BLK+FG%)".
NAMED_PUNT_PAIRS = [["FT_IMPACT", "TOV"], ["FG_IMPACT", "3PM"], ["BLK", "FG_IMPACT"]]


def pool_percentage_means(df: pd.DataFrame, pool_ids: list[str]) -> tuple[float, float]:
    """§4.2's pool_mean_FG% / pool_mean_FT%: volume-weighted (total makes /
    total attempts across the pool), not a plain average of percentages --
    otherwise a low-volume shooter's rate would count as much as a star's,
    which defeats the point of a volume-weighted impact metric."""
    pool = df.loc[pool_ids]
    fg_mean = (pool["FG_PCT"] * pool["FGA"]).sum() / pool["FGA"].sum()
    ft_mean = (pool["FT_PCT"] * pool["FTA"]).sum() / pool["FTA"].sum()
    return fg_mean, ft_mean


def add_percentage_impact_with_baseline(df: pd.DataFrame, fg_mean: float, ft_mean: float) -> pd.DataFrame:
    """Like add_percentage_impact, but applies an externally supplied
    (fg_mean, ft_mean) baseline instead of deriving one from `df`'s own
    pool. Used by the backtest (src/backtest.py) to apply one fixed,
    actual-outcome baseline across the actual/projected comparison, so
    IMPACT differences there reflect each player's own projected rate and
    volume, not pool-mean drift between scenarios."""
    out = df.copy()
    out["FG_IMPACT"] = (out["FG_PCT"].fillna(0) - fg_mean) * out["FGA"].fillna(0)
    out["FT_IMPACT"] = (out["FT_PCT"].fillna(0) - ft_mean) * out["FTA"].fillna(0)
    return out


def add_percentage_impact(projected: pd.DataFrame, pool_ids: list[str]) -> pd.DataFrame:
    """§4.2: FG_impact = (player_FG% - pool_mean_FG%) * player_FGA (same
    for FT), standardized -- never the raw percentage. A zero-attempt
    player lands at zero impact, the correct answer, and falls out
    naturally."""
    fg_mean, ft_mean = pool_percentage_means(projected, pool_ids)
    return add_percentage_impact_with_baseline(projected, fg_mean, ft_mean)


def zscore_value(with_impact: pd.DataFrame, pool_ids: list[str], punt: list[str] | None = None) -> pd.DataFrame:
    """§4.3: z_cat = (value - pool_mean) / pool_stdev, per category, over
    the draftable pool. Invert sign on TOV, sum the categories for VALUE.
    §4.5: punt categories are excluded entirely from standardization (not
    zeroed) so the remaining categories restandardize against each other --
    `value(player, punt_categories)`. Guards a near-zero pool stdev rather
    than dividing by it (possible on a tiny/degenerate pool)."""
    punt = set(punt or [])
    cats = [c for c in ALL_CATEGORIES if c not in punt]
    pool = with_impact.loc[pool_ids]

    out = with_impact.copy()
    z_cols = []
    for cat in cats:
        mean = pool[cat].mean()
        std = pool[cat].std(ddof=0)
        col = f"z_{cat}"
        if std < 1e-9:
            out[col] = 0.0
        else:
            z = (out[cat] - mean) / std
            out[col] = -z if cat in INVERTED_CATEGORIES else z
        z_cols.append(col)
    out["VALUE"] = out[z_cols].sum(axis=1)
    return out


def select_draftable_pool(
    projected: pd.DataFrame, pool_size: int = 150, max_iterations: int = 5
) -> tuple[list[str], int]:
    """§4.1: 'Resolve by iterating: seed on projected minutes, compute
    values, reselect the top 150 by value, recompute. Two or three passes
    converge. Cap at 5 and assert stability.'"""
    pool_ids = projected.sort_values("mpg", ascending=False).head(pool_size).index.tolist()
    for i in range(1, max_iterations + 1):
        with_impact = add_percentage_impact(projected, pool_ids)
        valued = zscore_value(with_impact, pool_ids, punt=[])
        new_pool = valued.sort_values("VALUE", ascending=False).head(pool_size).index.tolist()
        if set(new_pool) == set(pool_ids):
            return sorted(new_pool), i
        pool_ids = new_pool
    raise AssertionError(f"draftable pool did not stabilize within {max_iterations} iterations")


def value_players(projected: pd.DataFrame, pool_size: int = 150) -> tuple[pd.DataFrame, list[str], int]:
    """Full §4 balanced-build pipeline: draftable pool (§4.1) + percentage
    impact (§4.2) + Z-score (§4.3). Returns (valued_df, pool_ids,
    iterations_to_converge)."""
    pool_ids, iterations = select_draftable_pool(projected, pool_size)
    with_impact = add_percentage_impact(projected, pool_ids)
    valued = zscore_value(with_impact, pool_ids, punt=[])
    return valued, pool_ids, iterations


def all_punt_scenarios(categories: list[str] = ALL_CATEGORIES) -> list[list[str]]:
    """§4.5: 'ranks all single-category punts plus the common pairs.'
    [] (first entry) is the balanced build."""
    singles = [[c] for c in categories]
    return [[]] + singles + [list(pair) for pair in NAMED_PUNT_PAIRS]


def punt_report(with_impact: pd.DataFrame, pool_ids: list[str], top_n: int = 30) -> dict[str, pd.DataFrame]:
    """§4.5: '--punt-report mode that ranks all single-category punts plus
    the common pairs..., and for each shows the top 30 board and how much
    each player's rank moves versus the balanced build. Players who rise
    40+ spots under a given punt are that build's value targets.'"""
    balanced = zscore_value(with_impact, pool_ids, punt=[])
    balanced_board = balanced.loc[pool_ids].sort_values("VALUE", ascending=False)
    balanced_rank = pd.Series(range(1, len(balanced_board) + 1), index=balanced_board.index)

    reports = {}
    for punt in all_punt_scenarios():
        label = "balanced" if not punt else "+".join(punt)
        valued = zscore_value(with_impact, pool_ids, punt=punt)
        board = valued.loc[pool_ids].sort_values("VALUE", ascending=False).head(top_n).copy()
        board["rank_punt"] = range(1, len(board) + 1)
        board["rank_balanced"] = board.index.map(balanced_rank)
        board["rank_move"] = board["rank_balanced"] - board["rank_punt"]
        reports[label] = board
    return reports
