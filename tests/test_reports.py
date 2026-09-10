"""§9 stage 3: roster parsing + crosswalk reports (§2.3)."""

import pandas as pd
import pytest

from src import ingest, reports


@pytest.fixture(scope="module")
def data():
    return ingest.load_canonical(validate=False)


def test_crosswalk_report_passes_and_summarizes(data):
    summary = reports.crosswalk_report(data["rosters"], data["crosswalk_unmatched"])
    assert summary["unmatched_with_fuzzy_suggestion"] == 0
    assert summary["matched"] + summary["unmatched"] == summary["total_roster_entries"]
    assert summary["unmatched"] == len(data["crosswalk_unmatched"])


def test_crosswalk_report_raises_on_a_fuzzy_neighbour(data):
    dirty = data["crosswalk_unmatched"].copy()
    dirty["fuzzy_suggestion"] = dirty["fuzzy_suggestion"].astype(object)
    dirty.loc[dirty.index[0], "fuzzy_suggestion"] = "Some Player (someid01)"
    with pytest.raises(AssertionError):
        reports.crosswalk_report(data["rosters"], dirty)


def test_write_vacated_opportunity(tmp_path, data):
    from src import project

    table = project.compute_vacated_opportunity(data["player_team_seasons"], data["rosters"])
    out_path = reports.write_vacated_opportunity(table, path=tmp_path / "vacated_opportunity.csv")
    assert out_path.exists()
    reloaded = pd.read_csv(out_path)
    assert len(reloaded) == len(table)
