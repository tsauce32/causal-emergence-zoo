# RAS3 religion-policy pilot

This is the first empirical run of the CE2 narrative pipeline on a public social
system dataset. It uses the Religion and State Project Round 3 (RAS3) country
panel, which covers 183 countries and independent territories from 1990–2014.
The source is not bundled with this repository; download the labelled Stata file
from ARDA and run:

```console
python examples/ras3_religion_policy_pilot.py RAS3.dta
```

## Predeclared model

The pilot constructs one trajectory per country and one observation per year. It
uses seven RAS3 composite variables: official religion, religious regulation,
religious legislation, discrimination against minority religions, societal
discrimination, minority actions against the majority, and societal relations.
It retains only complete country-years and countries with at least 20 retained
years. No values are interpolated.

The reference run (RAS3 public download, 11 July 2026, seed 17) retained 173
countries and 4,296 country-years. With eight learned microstates and a strict
five-step random-walk consistency check (KL tolerance `1e-6`), it found:

| Quantity | Result |
| --- | --- |
| Microscale CP | 0.9482 |
| Endpoint partition | seven microstates merged; one singleton state |
| Endpoint CP | 1.0000 |
| CP gain | 0.0518 |
| Valid consistent partitions | 3 |

The isolated microstate is the learned profile with the highest average scores
for religious regulation, legislation, discrimination against minority
religions, and societal discrimination. The induced two-state macro TPM is the
identity matrix: this panel is overwhelmingly persistent year to year.

## Result: do not treat it as a substantive narrative yet

The positive gain is **not resolution-stable**. Repeating the strict analysis
with 3–7 learned microstates returns no positive macro gain; it appears only at
eight. The correct current conclusion is therefore that this annual RAS-only
panel supplies a valuable diagnostic benchmark, but does not yet justify a
robust claim of a causal macro-regime.

The next empirical design should add independently measured poverty/inequality
and social-capacity variables, assess held-out-country stability, and compare
against time-shuffled trajectories. The resulting claims must remain
model-derived descriptions of observed country-year configurations, not claims
that religion causes poverty or conflict.

