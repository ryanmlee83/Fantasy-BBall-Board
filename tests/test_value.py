"""§9 stage 6: §4 Z-score valuation with punt scenarios."""

import numpy as np
import pytest

from src import ingest, project, value


@pytest.fixture(scope="module")
def data():
    return ingest.load_canonical(validate=False)


@pytest.fixture(scope="module")
def projected(data):
    return project.project_players(data)


@pytest.fixture(scope="module")
def valued_pool(projected):
    valued, pool_ids, iterations = value.value_players(projected, pool_size=150)
    return valued, pool_ids, iterations


def test_draftable_pool_converges_and_is_right_size(valued_pool):
    valued, pool_ids, iterations = valued_pool
    assert len(pool_ids) == 150
    assert iterations <= 5


def test_zero_attempts_gives_zero_percentage_impact(projected):
    pool_ids = projected.index[:50].tolist()
    fabricated = projected.copy()
    fabricated.loc[pool_ids[0], ["FGA", "FTA"]] = 0.0
    with_impact = value.add_percentage_impact(fabricated, pool_ids)
    assert with_impact.loc[pool_ids[0], "FG_IMPACT"] == 0.0
    assert with_impact.loc[pool_ids[0], "FT_IMPACT"] == 0.0


def test_zscore_pool_mean_zero_std_one(valued_pool):
    """§4.3: 'z_cat = (value - pool_mean) / pool_stdev... over the
    draftable pool.' Sanity-check the pool's own z-scores are standardized."""
    valued, pool_ids, _ = valued_pool
    for cat in value.ALL_CATEGORIES:
        z = valued.loc[pool_ids, f"z_{cat}"]
        assert z.mean() == pytest.approx(0.0, abs=1e-6)
        assert z.std(ddof=0) == pytest.approx(1.0, abs=1e-6)


def test_turnover_sign_is_inverted(valued_pool):
    """§4.3: 'Invert the sign on turnovers' -- fewer TOV than the pool
    average must score positively, not negatively."""
    valued, pool_ids, _ = valued_pool
    pool = valued.loc[pool_ids]
    below_avg_tov = pool[pool["TOV"] < pool["TOV"].mean()]
    assert (below_avg_tov["z_TOV"] > 0).all()


def test_zero_stdev_category_does_not_raise():
    import pandas as pd

    df = pd.DataFrame(
        {c: [1.0, 1.0, 1.0] for c in value.ALL_CATEGORIES}, index=pd.Index(["a", "b", "c"], name="player_id")
    )
    result = value.zscore_value(df, ["a", "b", "c"], punt=[])
    assert (result[[f"z_{c}" for c in value.ALL_CATEGORIES]] == 0.0).all().all()


def test_punt_excludes_category_entirely_not_zeroes_it(projected):
    """§4.5: punted categories are excluded from restandardization, not
    zeroed -- called on a fresh (not-yet-valued) table, as cli.py does,
    the punted category gets no z-column at all, and the remaining eight
    restandardize (mean ~0, std ~1) on their own."""
    pool_ids = projected.sort_values("mpg", ascending=False).head(150).index.tolist()
    with_impact = value.add_percentage_impact(projected, pool_ids)
    punt_result = value.zscore_value(with_impact, pool_ids, punt=["TOV"])
    for cat in [c for c in value.ALL_CATEGORIES if c != "TOV"]:
        z = punt_result.loc[pool_ids, f"z_{cat}"]
        assert z.mean() == pytest.approx(0.0, abs=1e-6)
    assert "z_TOV" not in punt_result.columns


def test_all_punt_scenarios_include_named_pairs_and_all_singles():
    scenarios = value.all_punt_scenarios()
    assert [] in scenarios
    for cat in value.ALL_CATEGORIES:
        assert [cat] in scenarios
    for pair in value.NAMED_PUNT_PAIRS:
        assert pair in scenarios


def test_punt_report_shows_rank_movement(projected):
    valued, pool_ids, _ = value.value_players(projected, pool_size=150)
    with_impact = value.add_percentage_impact(projected, pool_ids)
    reports = value.punt_report(with_impact, pool_ids, top_n=30)

    assert "balanced" in reports
    assert set(reports) == {"balanced"} | {c for c in value.ALL_CATEGORIES} | {
        "+".join(p) for p in value.NAMED_PUNT_PAIRS
    }
    # At least one punt scenario should move somebody's rank meaningfully --
    # otherwise punting would be pointless, which we know isn't the case
    # (§4.5: "Players who rise 40+ spots under a given punt are that
    # build's value targets").
    max_move = max(board["rank_move"].abs().max() for label, board in reports.items() if label != "balanced")
    assert max_move >= 10
