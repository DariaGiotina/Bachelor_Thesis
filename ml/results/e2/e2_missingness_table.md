# E2 (Task 3.5): missing answers by field, natural missingness and curve

Seeds: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]. SCIN test split. Test macro-F1; differences are paired per seed (mean, t-based 95% CI over seeds, seeds where the difference is negative, Holm-adjusted p).

## Random removal (curve, `e2_curve.png`)

| arm | r = 0 | r = 0.25 | r = 0.5 | r = 0.75 | r = 1 |
|---|---|---|---|---|---|
| photo only | 0.519 ± 0.040 | 0.519 ± 0.040 | 0.519 ± 0.040 | 0.519 ± 0.040 | 0.519 ± 0.040 |
| concat, no dropout | 0.505 ± 0.036 | 0.506 ± 0.035 | 0.506 ± 0.039 | 0.499 ± 0.036 | 0.504 ± 0.035 |
| concat, fixed dropout | 0.514 ± 0.040 | 0.508 ± 0.043 | 0.511 ± 0.042 | 0.508 ± 0.036 | 0.505 ± 0.042 |
| concat, random dropout | 0.510 ± 0.037 | 0.509 ± 0.037 | 0.508 ± 0.040 | 0.508 ± 0.038 | 0.507 ± 0.039 |
| FiLM, fixed dropout | 0.519 ± 0.044 | 0.519 ± 0.038 | 0.518 ± 0.038 | 0.522 ± 0.036 | 0.513 ± 0.034 |

## One field hidden for every case (change vs all answers kept)

| field | concat, no dropout | concat, fixed dropout | concat, random dropout | FiLM, fixed dropout |
|---|---|---|---|---|
| age_group | +0.002 [-0.011, +0.014] 6/10 | -0.001 [-0.009, +0.007] 5/10 | -0.001 [-0.002, +0.001] 5/10 | +0.008 [-0.009, +0.024] 5/10 |
| body_area | -0.004 [-0.016, +0.008] 4/10 | -0.002 [-0.012, +0.007] 7/10 | +0.001 [-0.002, +0.004] 3/10 | -0.002 [-0.016, +0.012] 5/10 |
| duration | +0.002 [-0.008, +0.011] 6/10 | -0.005 [-0.015, +0.006] 8/10 | +0.000 [-0.002, +0.003] 5/10 | -0.003 [-0.015, +0.009] 5/10 |
| skin_type | +0.002 [-0.004, +0.008] 4/10 | -0.003 [-0.008, +0.003] 6/10 | +0.000 [-0.003, +0.003] 5/10 | +0.001 [-0.009, +0.012] 7/10 |
| symptoms | -0.008 [-0.016, +0.001] 8/10 | -0.003 [-0.006, +0.001] 5/10 | -0.003 [-0.006, -0.000] 6/10 | -0.005 [-0.018, +0.008] 7/10 |
| texture | -0.000 [-0.006, +0.006] 4/10 | -0.000 [-0.010, +0.009] 5/10 | +0.002 [-0.002, +0.006] 4/10 | -0.007 [-0.024, +0.010] 8/10 |
| whole questionnaire | -0.001 [-0.016, +0.014] 7/10 | -0.009 [-0.022, +0.003] 7/10 | -0.004 [-0.012, +0.005] 6/10 | -0.007 [-0.027, +0.013] 7/10 |

## Only one field kept (change vs all answers kept)

| field | concat, no dropout | concat, fixed dropout | concat, random dropout | FiLM, fixed dropout |
|---|---|---|---|---|
| age_group | -0.003 [-0.014, +0.009] 7/10 | -0.007 [-0.022, +0.009] 7/10 | +0.000 [-0.006, +0.007] 5/10 | -0.010 [-0.034, +0.013] 8/10 |
| body_area | -0.005 [-0.022, +0.012] 7/10 | -0.006 [-0.013, +0.002] 5/10 | +0.001 [-0.006, +0.007] 4/10 | -0.002 [-0.020, +0.016] 7/10 |
| duration | -0.004 [-0.018, +0.010] 7/10 | -0.004 [-0.019, +0.010] 9/10 | -0.005 [-0.011, -0.000] 9/10 | -0.003 [-0.028, +0.023] 6/10 |
| skin_type | -0.001 [-0.017, +0.015] 7/10 | -0.006 [-0.017, +0.004] 7/10 | -0.004 [-0.009, +0.002] 6/10 | -0.003 [-0.022, +0.016] 5/10 |
| symptoms | -0.003 [-0.017, +0.011] 7/10 | -0.005 [-0.018, +0.009] 8/10 | -0.004 [-0.008, +0.001] 8/10 | +0.003 [-0.018, +0.024] 5/10 |
| texture | -0.004 [-0.018, +0.010] 7/10 | -0.007 [-0.023, +0.009] 7/10 | -0.004 [-0.010, +0.002] 7/10 | -0.005 [-0.028, +0.019] 7/10 |

\* Holm-adjusted p < 0.05 (within one arm and one condition type).

## Naturally missing answers in SCIN (fusion minus photo-only, same cases, r = 0)

| group | test cases per seed | photo only | concat, no dropout | concat, fixed dropout | concat, random dropout | FiLM, fixed dropout |
|---|---|---|---|---|---|---|
| complete | 139 | 0.511 | 0.504 (-0.007 [-0.041, +0.026]) | 0.494 (-0.017 [-0.066, +0.031]) | 0.490 (-0.021 [-0.053, +0.012]) | 0.525 (+0.014 [-0.015, +0.042]) |
| partial | 95 | 0.523 | 0.506 (-0.017 [-0.039, +0.005]) | 0.521 (-0.002 [-0.029, +0.025]) | 0.519 (-0.005 [-0.025, +0.016]) | 0.489 (-0.035 [-0.089, +0.019]) |
| empty | 37 | 0.504 | 0.463 (-0.041 [-0.097, +0.014]) | 0.514 (+0.009 [-0.026, +0.045]) | 0.511 (+0.006 [-0.033, +0.046]) | 0.507 (+0.002 [-0.047, +0.052]) |

complete = every field that can be skipped is answered; partial = some skipped; empty = all of them skipped (the age question is left out of this count: it always has an answer, because 'age unknown' is encoded as an explicit answer, not as missing). Groups under 30 cases are marked small.
