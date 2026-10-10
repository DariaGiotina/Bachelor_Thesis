# Ceiling: a synthetic question independent of the photo, in the stacking combiner

Seeds [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]. Test macro-F1, mean ± sd over seeds; gain = with the question minus photo only (same out-of-fold photo predictions); seeds better = seeds with a positive gain.

| agreement | question alone | photo only (stack_photo) | photo + question | gain | seeds better |
|---|---|---|---|---|---|
| 0.2 | 0.305 | 0.496 | 0.493 ± 0.046 | -0.003 ± 0.035 | 4/10 |
| 0.3 | 0.363 | 0.496 | 0.513 ± 0.048 | +0.017 ± 0.036 | 6/10 |
| 0.4 | 0.417 | 0.496 | 0.535 ± 0.050 | +0.039 ± 0.046 | 8/10 |
| 0.5 | 0.485 | 0.496 | 0.577 ± 0.047 | +0.081 ± 0.046 | 10/10 |
