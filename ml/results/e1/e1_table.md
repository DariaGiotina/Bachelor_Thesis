# E1: photo only vs questionnaire only vs fusion (test, seeds [0, 1, 2, 3, 4])

Backbone efficientnet_b0, imbalance correction weighted_loss. Each cell: mean ± sd over seeds [95% seed-stratified case-bootstrap CI].

| Arm | Macro-F1 | Balanced accuracy | ECE | Macro-F1, all answers hidden |
|---|---|---|---|---|
| image_only | 0.537 ± 0.038 [0.493, 0.572] | 0.624 ± 0.044 [0.585, 0.661] | 0.070 ± 0.012 [0.051, 0.089] | n/a |
| questionnaire_only | 0.390 ± 0.038 [0.344, 0.428] | 0.443 ± 0.043 [0.388, 0.494] | 0.083 ± 0.020 [0.064, 0.104] | 0.145 ± 0.037 [0.138, 0.152] |
| fusion_concat | 0.516 ± 0.057 [0.468, 0.551] | 0.595 ± 0.038 [0.550, 0.637] | 0.088 ± 0.056 [0.067, 0.110] | 0.506 ± 0.060 [0.461, 0.540] |
| fusion_gated | 0.514 ± 0.040 [0.464, 0.550] | 0.582 ± 0.065 [0.534, 0.629] | 0.088 ± 0.021 [0.067, 0.110] | 0.521 ± 0.043 [0.473, 0.556] |
| fusion_film | 0.544 ± 0.043 [0.497, 0.579] | 0.611 ± 0.058 [0.565, 0.654] | 0.085 ± 0.028 [0.067, 0.105] | 0.518 ± 0.049 [0.473, 0.552] |
| fusion_concat_nodrop | 0.503 ± 0.046 [0.456, 0.538] | 0.582 ± 0.035 [0.536, 0.623] | 0.088 ± 0.048 [0.069, 0.109] | 0.495 ± 0.048 [0.448, 0.529] |
| ensemble_image_q | 0.521 ± 0.035 [0.470, 0.556] | 0.574 ± 0.069 [0.527, 0.616] | 0.081 ± 0.022 [0.062, 0.101] | 0.549 ± 0.044 [0.506, 0.582] |

Paired macro-F1 difference A - B on the shared test cases (per seed, mean with seed-stratified paired bootstrap CI, seeds where A is better, paired t-test and Wilcoxon p over seeds).

| A | B | seed 0 | seed 1 | seed 2 | seed 3 | seed 4 | Mean [95% CI] | A better | t p | Wilcoxon p |
|---|---|---|---|---|---|---|---|---|---|---|
| fusion_concat | image_only | -0.053 | +0.018 | +0.003 | -0.049 | -0.025 | -0.021 [-0.051, +0.007] | 2/5 | 0.203 | 0.312 |
| fusion_concat | questionnaire_only | +0.093 | +0.184 | +0.079 | +0.145 | +0.126 | +0.126 [+0.071, +0.178] | 5/5 | 0.003 | 0.062 |
| fusion_gated | image_only | +0.007 | +0.005 | -0.017 | -0.062 | -0.048 | -0.023 [-0.060, +0.011] | 2/5 | 0.170 | 0.312 |
| fusion_gated | questionnaire_only | +0.152 | +0.171 | +0.059 | +0.131 | +0.104 | +0.124 [+0.070, +0.175] | 5/5 | 0.003 | 0.062 |
| fusion_film | image_only | +0.045 | +0.018 | +0.028 | -0.004 | -0.049 | +0.008 [-0.023, +0.038] | 3/5 | 0.662 | 0.812 |
| fusion_film | questionnaire_only | +0.191 | +0.184 | +0.104 | +0.190 | +0.102 | +0.154 [+0.104, +0.205] | 5/5 | 0.002 | 0.062 |
| fusion_concat_nodrop | image_only | -0.055 | -0.033 | -0.023 | -0.027 | -0.029 | -0.033 [-0.067, -0.002] | 0/5 | 0.004 | 0.062 |
| fusion_concat_nodrop | questionnaire_only | +0.091 | +0.133 | +0.053 | +0.167 | +0.122 | +0.113 [+0.063, +0.165] | 5/5 | 0.004 | 0.062 |
| ensemble_image_q | image_only | -0.005 | -0.057 | -0.019 | +0.000 | +0.002 | -0.016 [-0.053, +0.018] | 1/5 | 0.224 | 0.250 |
| ensemble_image_q | questionnaire_only | +0.141 | +0.109 | +0.057 | +0.194 | +0.153 | +0.131 [+0.086, +0.177] | 5/5 | 0.005 | 0.062 |
| image_only | questionnaire_only | +0.146 | +0.166 | +0.076 | +0.194 | +0.151 | +0.147 [+0.096, +0.199] | 5/5 | 0.002 | 0.062 |
| fusion_gated | fusion_concat | +0.059 | -0.013 | -0.020 | -0.014 | -0.023 | -0.002 [-0.035, +0.027] | 1/5 | 0.903 | 0.625 |
| fusion_film | fusion_concat | +0.098 | -0.000 | +0.025 | +0.045 | -0.024 | +0.029 [-0.002, +0.060] | 3/5 | 0.238 | 0.312 |
| fusion_concat_nodrop | fusion_concat | -0.002 | -0.051 | -0.026 | +0.022 | -0.004 | -0.012 [-0.036, +0.011] | 1/5 | 0.377 | 0.312 |
| ensemble_image_q | fusion_concat | +0.048 | -0.075 | -0.022 | +0.049 | +0.027 | +0.005 [-0.037, +0.047] | 3/5 | 0.831 | 0.812 |

The CI reflects test-set sampling (cases); the sd reflects training randomness (seeds). The ECE interval is bias-corrected (ECE is biased upward under resampling). With 5 seeds the Wilcoxon test cannot go below p = 0.0625.
