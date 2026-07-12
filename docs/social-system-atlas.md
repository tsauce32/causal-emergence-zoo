# Social-system atlas benchmark

The first domain benchmark for the narrative library is a country-year atlas
covering religion, poverty, inequality, social capacity, and violence. It is
assembled from public sources rather than treated as a single proprietary file:

- RAS3: religion policy and societal discrimination, 183 countries, 1990–2014;
- World Bank Poverty and Inequality Platform: poverty and inequality estimates;
- V-Dem Country-Year: political and social-capacity indicators;
- UCDP GED: country-year aggregates of organized-violence events and fatalities.

The recommended initial period is 1990–2014 because it matches RAS3. Download
the source files from their official portals, convert each to a long CSV with
`country_code,year,<numeric columns>`, then join them with:

```python
from causal_emergence_zoo.social_atlas import (
    assemble_social_atlas, load_country_year_source, write_social_atlas_csv,
)

atlas = assemble_social_atlas(
    [
        ("ras3", load_country_year_source("ras3.csv", prefix="ras_")),
        ("pip", load_country_year_source("pip.csv", prefix="pip_")),
        ("vdem", load_country_year_source("vdem.csv", prefix="vdem_")),
    ],
    feature_columns=[
        "ras_religious_restriction",
        "ras_societal_discrimination",
        "pip_poverty_headcount",
        "pip_gini",
        "vdem_civil_society",
        "vdem_electoral_democracy",
    ],
    start_year=1990,
    end_year=2014,
    min_observations=5,
)
write_social_atlas_csv(atlas, "social-atlas.csv")
```

The join performs complete-case filtering only; it never interpolates poverty,
religion, or political scores silently. The output records missingness,
retained countries, source names, and the exact feature list. This matters
because survey years and expert-coded indicators are not equally observed.

After writing the atlas, run the existing continuous analyzer with
`trajectory_column=country_code`, `time_column=year`, and a deliberately small
microstate budget first. Treat the resulting narrative as a model-derived
description of country-year configurations. It is not an interventionally
identified claim that religion causes poverty, or that poverty causes conflict.

