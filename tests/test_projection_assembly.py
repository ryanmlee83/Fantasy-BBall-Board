"""§9 stage 5: §3 projection assembly."""

import pandas as pd
import pytest

from src import ingest, project


@pytest.fixture(scope="module")
def data():
    return ingest.load_canonical(validate=False)


@pytest.fixture(scope="module")
def config():
    return project.load_league_config()


def test_blend_seasons_renormalizes_over_available_seasons():
    """§3.2: a player with only one available season should get that
    season's raw rate back, not a weight-diluted fraction of it."""
    rows = pd.DataFrame(
        [
            {"player_id": "p1", "season": "2025-26", "mp": 1000, "pts_p100": 30.0, "pos": "PG"},
        ]
    )
    for col in project._ALL_COLS:
        if col not in rows.columns:
            rows[col] = None
    rows["pts_p100"] = 30.0

    blended = project.blend_seasons(rows, ["p1"], {"2025-26": 0.5, "2024-25": 0.3, "2023-24": 0.2})
    assert blended.loc["p1", "blended_pts_p100"] == pytest.approx(30.0)
    assert blended.loc["p1", "mp_total"] == 1000


def test_blend_seasons_weights_by_minutes_within_season():
    """§3.2: 'a 200-minute season contributes less than a 2,400-minute one
    even at equal season weight.'"""
    rows = pd.DataFrame(
        [
            {"player_id": "p1", "season": "2024-25", "mp": 200, "pts_p100": 10.0, "pos": "PG"},
            {"player_id": "p1", "season": "2023-24", "mp": 2400, "pts_p100": 30.0, "pos": "PG"},
        ]
    )
    for col in project._ALL_COLS:
        if col not in rows.columns:
            rows[col] = None
    rows.loc[rows["season"] == "2024-25", "pts_p100"] = 10.0
    rows.loc[rows["season"] == "2023-24", "pts_p100"] = 30.0

    blended = project.blend_seasons(rows, ["p1"], {"2024-25": 0.3, "2023-24": 0.2})
    # Equal season weights would give 20.0; minutes-weighting should pull it
    # much closer to the high-minutes season's 30.0.
    assert blended.loc["p1", "blended_pts_p100"] > 25.0


def test_regress_to_mean_falls_back_to_baseline_at_zero_minutes():
    """§3.3: shrunk = (MP_total*observed + K*baseline) / (MP_total + K).
    At MP_total=0 the result must equal the baseline exactly."""
    blended = pd.DataFrame(
        {"blended_pts_p100": [50.0], "mp_total": [0], "pos": ["PG"]}, index=pd.Index(["p1"], name="player_id")
    )
    for col in project._ALL_COLS:
        if f"blended_{col}" not in blended.columns:
            blended[f"blended_{col}"] = None
    baselines = pd.DataFrame({col: [20.0] for col in project._ALL_COLS}, index=pd.Index(["PG"]))
    regression_k = {label: 500 for label in project.CATEGORY_COLUMNS}

    shrunk = project.regress_to_mean(blended, baselines, regression_k)
    assert shrunk.loc["p1", "shrunk_pts_p100"] == pytest.approx(20.0)


def test_age_curve_peak_multiplier_is_one():
    curve = project.AGE_CURVE_DEFAULT
    assert project._interp_curve(curve, 26) == pytest.approx(1.0)


def test_age_curve_declines_for_veterans():
    curve = project.AGE_CURVE_DEFAULT
    assert project._interp_curve(curve, 38) < project._interp_curve(curve, 27)


def test_age_curve_stl_blk_decay_faster_than_ast_ft_late_30s():
    early = project.AGE_CURVE_EARLY_DECAY
    late = project.AGE_CURVE_LATE_DECAY
    assert project._interp_curve(early, 35) < project._interp_curve(late, 35)


def test_generate_minutes_config_flags_every_player_estimated(tmp_path, data):
    path = tmp_path / "minutes.yaml"
    project.generate_minutes_config(data["rosters"], data["player_seasons"], path)
    cfg = project.load_minutes_config(path)
    matched = data["rosters"].dropna(subset=["player_id"])["player_id"].nunique()
    assert len(cfg) == matched
    assert all(v["estimated"] is True for v in cfg.values())
    assert all(v["mpg"] > 0 for v in cfg.values())


def test_generate_games_played_config_defaults_to_82(tmp_path, data):
    path = tmp_path / "gp.yaml"
    project.generate_games_played_config(data["rosters"], path)
    cfg = project.load_games_played_config(path)
    assert all(v["gp"] == 82 and v["estimated"] is True for v in cfg.values())


def test_minutes_sanity_check_discriminates_reviewed_from_naive(data):
    """The §3.5 check must separate reviewed rosters from naive ones.

    This deliberately does NOT assert how many teams pass. It used to assert
    fewer than 15, which encoded the state of the project at the time the test
    was written -- every team still on naive last-season MPG, which overshoots
    240x82 badly because per-player defaults ignore teammates. That number
    flips as review proceeds (it is 22 once 29 teams are filled from depth
    charts), so asserting it means the test fails on progress. The same stale
    -assumption bug was fixed once already in this file.

    What is actually invariant: the check covers all 30 teams, computes a real
    percentage against the documented target, and a naive roster overshoots.
    """
    minutes_cfg = project.load_minutes_config()
    gp_cfg = project.load_games_played_config()
    sanity = project.minutes_sanity_check(data["rosters"], minutes_cfg, gp_cfg)

    assert len(sanity) == 30
    assert set(sanity.columns) >= {"team", "total_projected_minutes", "target",
                                   "pct_of_target", "within_3pct"}
    assert (sanity["target"] == 240 * 82).all()
    assert (sanity["total_projected_minutes"] > 0).all()
    assert sanity["within_3pct"].equals(
        sanity["total_projected_minutes"].between(240 * 82 * 0.97, 240 * 82 * 1.03)
    )

    # A roster left on naive per-player defaults overshoots, by construction:
    # summing each player's own last-season MPG ignores that they compete for
    # the same 240 minutes.
    naive = {pid: {"mpg": 30.0, "estimated": True} for pid in minutes_cfg}
    naive_gp = {pid: {"gp": 82, "estimated": True} for pid in gp_cfg}
    naive_sanity = project.minutes_sanity_check(data["rosters"], naive, naive_gp)
    assert (naive_sanity["pct_of_target"] > 103).all()


def test_project_players_produces_expected_columns_and_no_nulls(data, config):
    projected = project.project_players(data, config)
    for col in ["PTS", "REB", "AST", "STL", "BLK", "3PM", "TOV", "FG_PCT", "FT_PCT", "FGA", "FTA", "mpg", "gp"]:
        assert col in projected.columns
        assert projected[col].notna().all()
    assert len(projected) > 400  # roughly the matched-rostered-player count
    # minutes_estimated/gp_estimated track manual-review progress (§3.5) and
    # legitimately flip from True to False as config/minutes.yaml and
    # config/games_played.yaml get filled in team by team -- assert they're
    # present and well-formed, not that they hold any particular value.
    assert projected["minutes_estimated"].isin([True, False]).all()
    assert projected["gp_estimated"].isin([True, False]).all()


def test_project_players_pts_in_plausible_range(data, config):
    projected = project.project_players(data, config)
    # No real NBA rotation player projects negative or absurdly high PTS.
    assert projected["PTS"].min() >= 0
    assert projected["PTS"].max() < 45
