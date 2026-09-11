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


def test_minutes_sanity_check_flags_most_teams_with_naive_defaults(data):
    """Naive last-season-MPG defaults, applied independently per player
    without accounting for teammates, should badly overshoot 240x82 for
    most rosters -- this is the expected, documented failure mode of
    skipping the human minutes-editing step (§3.5), not a bug."""
    minutes_cfg = project.load_minutes_config()
    gp_cfg = project.load_games_played_config()
    sanity = project.minutes_sanity_check(data["rosters"], minutes_cfg, gp_cfg)
    assert len(sanity) == 30
    assert sanity["within_3pct"].sum() < 15  # well under half, by construction


def test_project_players_produces_expected_columns_and_no_nulls(data, config):
    projected = project.project_players(data, config)
    for col in ["PTS", "REB", "AST", "STL", "BLK", "3PM", "TOV", "FG_PCT", "FT_PCT", "FGA", "FTA", "mpg", "gp"]:
        assert col in projected.columns
        assert projected[col].notna().all()
    assert len(projected) > 400  # roughly the matched-rostered-player count
    assert projected["minutes_estimated"].all()  # per this session's explicit instruction
    assert projected["gp_estimated"].all()


def test_project_players_pts_in_plausible_range(data, config):
    projected = project.project_players(data, config)
    # No real NBA rotation player projects negative or absurdly high PTS.
    assert projected["PTS"].min() >= 0
    assert projected["PTS"].max() < 45
