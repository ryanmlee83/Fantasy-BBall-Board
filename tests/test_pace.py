"""§9 stage 2: §3.4 pace + §8.3."""

import numpy as np
import pytest

from src import ingest, project


@pytest.fixture(scope="module")
def data():
    return ingest.load_canonical(validate=False)


@pytest.fixture(scope="module")
def pace_table(data):
    return project.compute_pace_table(data["player_team_seasons"], data["team_seasons"])


def test_matches_canonical_team_seasons(data, pace_table):
    canonical = data["team_seasons"].set_index("team").sort_index()
    computed = pace_table.set_index("team").sort_index()

    assert np.allclose(computed["pace_simple"], canonical["pace_simple"], atol=0.01)
    assert np.allclose(computed["pace_implied"], canonical["pace_implied"], atol=0.05)
    assert np.allclose(computed["minutes_share"], canonical["minutes_share"], atol=0.001)


def test_league_average_implied_pace_99_4(pace_table):
    avg = pace_table["pace_implied"].mean()
    assert 99.2 <= avg <= 99.6


def test_implied_simple_ratio_about_0_969(pace_table):
    ratio = pace_table["pace_implied"].mean() / pace_table["pace_simple"].mean()
    assert 0.96 <= ratio <= 0.98


def test_implied_simple_correlation_about_0_97(pace_table):
    corr = pace_table["pace_implied"].corr(pace_table["pace_simple"])
    assert corr >= 0.95


def test_minutes_share_100_to_101_pct(pace_table):
    assert pace_table["minutes_share"].between(0.99, 1.02).all()


def test_project_team_pace_defaults_to_2526_implied(data):
    projected = project.project_team_pace_2627(data["team_seasons"], overrides={})
    canonical = data["team_seasons"].set_index("team")["pace_implied"]
    assert np.allclose(projected.sort_index(), canonical.sort_index())


def test_project_team_pace_applies_overrides(data):
    projected = project.project_team_pace_2627(data["team_seasons"], overrides={"BOS": 101.5})
    assert projected["BOS"] == 101.5


def test_pace_warns_outside_95_104(capsys, data):
    team_seasons = data["team_seasons"].copy()
    team_seasons["pts_pg"] = team_seasons["pts_pg"] * 2  # force implied pace out of range
    project.compute_pace_table(data["player_team_seasons"], team_seasons)
    assert "WARNING" in capsys.readouterr().out
