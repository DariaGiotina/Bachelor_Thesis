# Positive control: fusion with one synthetic informative question

Seeds [0, 1, 2]. agreement = share of cases whose synthetic answer is the true category (otherwise a random category). r = share of questions hidden at test time.

| agreement | r | synthetic answer alone | photo only | fusion | fusion - photo |
|---|---|---|---|---|---|
| 0.3 | 0 | 0.380 | 0.527 | 0.532 ± 0.024 | +0.005 |
| 0.3 | 1 | 0.380 | 0.527 | 0.505 ± 0.020 | -0.022 |
| 0.5 | 0 | 0.501 | 0.527 | 0.635 ± 0.051 | +0.108 |
| 0.5 | 1 | 0.501 | 0.527 | 0.502 ± 0.067 | -0.026 |
