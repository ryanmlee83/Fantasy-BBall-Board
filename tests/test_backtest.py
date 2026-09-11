"""§9 stage 7: §8.4 backtest."""

import pytest

from src import backtest, ingest, project


@pytest.fixture(scope="module")
def data():
    return ingest.load_canonical(validate=False)


@pytest.fixture(scope="module")
def config():
    return project.load_league_config()


@pytest.fixture(scope="module")
def results(data, config):
    return backtest.run_backtest(data, config)


def test_backtest_population_excludes_multi_team_players(data):
    pop = backtest.backtest_population(data["player_seasons"])
    assert not pop["multi_team"].any()


def test_backtest_population_requires_training_history(data):
    pop = backtest.backtest_population(data["player_seasons"])
    ps = data["player_seasons"]
    train_ids = set(ps.loc[ps["season"].isin(backtest.TRAIN_SEASONS), "player_id"])
    assert set(pop.index) <= train_ids


def test_run_backtest_tables_share_the_same_players(results):
    actual, proj = results["actual"], results["projected_actual_minutes"]
    assert len(actual) > 300
    assert set(actual.index) == set(proj.index)


def test_actual_minutes_scenario_beats_proxy_on_counting_categories(results):
    """§8.4 caveat: 'Report backtest error both with actual minutes and
    with previous-season minutes as a naive proxy. The gap between those
    two numbers is the value of doing the minutes work well, and it will
    be large.' Knowing real playing time should out-predict guessing it."""
    actual = results["actual"]
    score_actual = backtest.score_backtest(actual, results["projected_actual_minutes"])
    score_proxy = backtest.score_backtest(actual, results["projected_proxy_minutes"])
    for cat in ["PTS", "REB", "AST", "TOV", "3PM"]:
        assert score_actual.loc[cat, "mae"] < score_proxy.loc[cat, "mae"]
        assert score_actual.loc[cat, "corr"] > score_proxy.loc[cat, "corr"]


def test_percentage_categories_are_minutes_invariant(results):
    """FG_PCT/FT_PCT don't get pace/minutes-scaled in §3.7 assembly, so
    both minutes scenarios must score identically on them -- a real
    difference here would mean a scenario leaked into the rate calc."""
    actual = results["actual"]
    score_actual = backtest.score_backtest(actual, results["projected_actual_minutes"])
    score_proxy = backtest.score_backtest(actual, results["projected_proxy_minutes"])
    for cat in ["FG_PCT", "FT_PCT"]:
        assert score_actual.loc[cat, "mae"] == pytest.approx(score_proxy.loc[cat, "mae"])


def test_largest_misses_shape(results):
    actual = results["actual"]
    misses = backtest.largest_misses(actual, results["projected_actual_minutes"], "PTS", n=20)
    assert len(misses) == 40
    assert set(misses["direction"]) == {"overprojected", "underprojected"}
    over = misses[misses["direction"] == "overprojected"]["error"]
    under = misses[misses["direction"] == "underprojected"]["error"]
    assert (over >= 0).all()
    assert (under <= 0).all()


def test_grid_search_returns_all_categories_and_improves_or_ties_default(data, config):
    # Small grid for test speed -- this is a correctness/shape check, not
    # a search for the true optimum (see reports/backtest.md for that).
    small_grid = [200, 500, 900, 1400]
    tuned_k, comparison = backtest.grid_search_regression_k(data, config, k_grid=small_grid)
    assert set(tuned_k) == set(project.CATEGORY_COLUMNS)
    assert len(comparison) == 9
    # A grid search can never do worse than its own default point, since
    # the default is always included in the evaluated set.
    assert (comparison["tuned_mae"] <= comparison["default_mae"] + 1e-9).all()
