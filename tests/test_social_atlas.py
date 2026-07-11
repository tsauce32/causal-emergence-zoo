import json

import pytest

from causal_emergence_zoo.social_atlas import (
    assemble_social_atlas,
    load_country_year_source,
    write_social_atlas_csv,
)


def test_social_atlas_joins_sources_and_preserves_missingness(tmp_path):
    poverty = tmp_path / "poverty.csv"
    poverty.write_text(
        "country_code,year,poverty,gini\nA,2000,20,40\nA,2001,18,39\nA,2002,,38\nB,2000,50,55\nB,2001,48,54\n",
        encoding="utf-8",
    )
    religion = tmp_path / "religion.csv"
    religion.write_text(
        "country_code,year,restriction\nA,2000,3\nA,2001,4\nA,2002,4\nB,2000,7\nB,2001,7\n",
        encoding="utf-8",
    )

    atlas = assemble_social_atlas(
        [("pip", load_country_year_source(poverty)), ("ras", load_country_year_source(religion))],
        feature_columns=["poverty", "gini", "restriction"],
        start_year=2000,
        end_year=2002,
        min_observations=2,
    )

    assert atlas["retained_countries"] == ["A", "B"]
    assert atlas["observation_count"] == 4
    assert atlas["missing_by_feature_before_complete_case_filter"]["poverty"] == 2
    output = tmp_path / "atlas.csv"
    write_social_atlas_csv(atlas, output)
    assert output.read_text(encoding="utf-8").splitlines()[0] == "country_code,year,poverty,gini,restriction"
    json.dumps(atlas, allow_nan=False)


def test_source_loader_rejects_duplicate_keys(tmp_path):
    source = tmp_path / "duplicate.csv"
    source.write_text("country_code,year,x\nA,2000,1\nA,2000,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_country_year_source(source)
