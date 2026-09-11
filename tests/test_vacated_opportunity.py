"""§9 stage 4: vacated_opportunity.csv (§3.5)."""

import numpy as np
import pytest

from src import ingest, project


@pytest.fixture(scope="module")
def data():
    return ingest.load_canonical(validate=False)


@pytest.fixture(scope="module")
def vacated(data):
    return project.compute_vacated_opportunity(data["player_team_seasons"], data["rosters"])


def test_covers_all_30_teams(vacated):
    assert len(vacated) == 30


def test_matches_canonical_reference(data, vacated):
    computed = vacated.set_index("team").sort_index()
    canonical = data["vacated_opportunity_canonical"].set_index("team").sort_index()

    assert list(computed.index) == list(canonical.index)
    assert np.allclose(computed["mp_2526_single_team"], canonical["mp_2526_single_team"], atol=1.0)
    assert np.allclose(computed["mp_vacated"], canonical["mp_vacated"], atol=1.0)
    assert np.allclose(computed["pct_vacated"], canonical["pct_vacated"], atol=0.5)
    assert (computed["n_departed"] == canonical["n_departed"]).all()


def test_usage_weighted_columns_match_canonical(data, vacated):
    """player_team_seasons.csv now carries per-stint usg_pct, and
    vacated_opportunity.csv adds usg_wtd_vacated / usg_minutes_vacated --
    per DATA_DICTIONARY.md, usg_minutes_vacated is "the metric spec §3.5
    calls for" (usage x minutes freed), since it distinguishes vacating
    many low-usage minutes from fewer high-usage ones."""
    computed = vacated.set_index("team").sort_index()
    canonical = data["vacated_opportunity_canonical"].set_index("team").sort_index()

    assert "usg_wtd_vacated" in canonical.columns
    assert "usg_minutes_vacated" in canonical.columns
    assert np.allclose(computed["usg_wtd_vacated"], canonical["usg_wtd_vacated"], atol=0.5)
    assert np.allclose(computed["usg_minutes_vacated"], canonical["usg_minutes_vacated"], atol=2.0)


def test_usg_minutes_vacated_and_mp_vacated_can_disagree_in_rank(vacated):
    # DATA_DICTIONARY.md: "Observed rank disagreements of up to 9 places
    # between the two." Confirms usage-weighting is doing real work, not
    # just tracking minutes linearly.
    by_mp = vacated.sort_values("mp_vacated", ascending=False)["team"].tolist()
    by_usg_minutes = vacated.sort_values("usg_minutes_vacated", ascending=False)["team"].tolist()
    rank_shift = max(abs(by_mp.index(t) - by_usg_minutes.index(t)) for t in by_mp)
    assert rank_shift >= 1


def test_pct_vacated_in_observed_range(vacated):
    # DATA_DICTIONARY.md: "Observed range 6.2% to 57.6%".
    assert vacated["pct_vacated"].min() >= 6.0
    assert vacated["pct_vacated"].max() <= 58.0


def test_sorted_by_minutes_vacated_descending(vacated):
    assert vacated["mp_vacated"].is_monotonic_decreasing
