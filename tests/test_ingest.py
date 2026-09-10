"""§9 stage 1: §2 ingestion + §8.1-8.2 invariants."""

import pytest

from src import ingest


@pytest.fixture(scope="module")
def data():
    return ingest.load_canonical(validate=False)


def test_season_counts(data):
    counts = data["player_seasons"].groupby("season")["player_id"].nunique()
    assert counts["2023-24"] == 572
    assert counts["2024-25"] == 569
    assert counts["2025-26"] == 582


def test_no_duplicate_player_season_rows(data):
    dupes = data["player_seasons"].duplicated(subset=["player_id", "season"])
    assert not dupes.any()


def test_802_distinct_players(data):
    assert data["player_seasons"]["player_id"].nunique() == 802


def test_374_common_to_all_three_seasons(data):
    by_season = {s: set(g["player_id"]) for s, g in data["player_seasons"].groupby("season")}
    assert len(set.intersection(*by_season.values())) == 374


def test_percentage_columns_blank_not_zero_when_no_attempts(data):
    ps = data["player_seasons"]
    zero_fta = ps[ps["fta_p100"] == 0]
    assert len(zero_fta) > 0  # sanity: the case actually occurs in this data
    assert zero_fta["ft_pct"].isna().all()


def test_team_blank_iff_multi_team(data):
    ps = data["player_seasons"]
    assert (ps["team"].isna() == ps["multi_team"]).all()


def test_ingestion_invariants_helper_passes(data):
    ingest.assert_ingestion_invariants(data["player_seasons"])


def test_ingestion_invariants_helper_catches_a_broken_count(data):
    broken = data["player_seasons"].copy()
    drop_idx = broken.index[broken["season"] == "2025-26"][0]
    broken = broken.drop(index=drop_idx)
    with pytest.raises(ingest.InvariantError):
        ingest.assert_ingestion_invariants(broken)


def test_join_integrity_age_plus_one(data):
    ingest.assert_join_integrity(data["player_seasons"])


def test_join_integrity_catches_a_broken_age(data):
    broken = data["player_seasons"].copy()
    mask = broken["season"] == "2025-26"
    broken.loc[mask, "age"] = broken.loc[mask, "age"] + 5
    with pytest.raises(ingest.InvariantError):
        ingest.assert_join_integrity(broken)


def test_load_canonical_validates_by_default():
    ingest.load_canonical(validate=True)  # should not raise
