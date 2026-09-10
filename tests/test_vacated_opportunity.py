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


def test_pct_vacated_in_observed_range(vacated):
    # DATA_DICTIONARY.md: "Observed range 6.2% to 57.6%".
    assert vacated["pct_vacated"].min() >= 6.0
    assert vacated["pct_vacated"].max() <= 58.0


def test_sorted_by_minutes_vacated_descending(vacated):
    assert vacated["mp_vacated"].is_monotonic_decreasing
