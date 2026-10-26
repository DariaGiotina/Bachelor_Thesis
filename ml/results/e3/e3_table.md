# E3 (Task 4.1, RQ3): results by skin tone

Seeds [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], stored test predictions (nothing retrained). Mean ± sd over seeds for a model; for differences the mean over seeds with a 95% paired bootstrap interval (cases resampled inside each group and seed). * = Holm-adjusted p < 0.05 within the model's family (all groups of both scales). (s) = fewer than 30 test cases per seed: descriptive only. n = mean test cases per seed. Gap = best minus worst macro-F1 group per seed, over groups with at least 20 cases (mean ± sd; noise in small groups inflates it, so compare it between models).

## SCIN test: macro-F1 by tone group

| Model | eFST I-II (n=117) | eFST III-IV (n=120) | eFST V-VI (n=23) | gap (worst group) |
|---|---|---|---|---|
| Photo, EfficientNet-B0 | 0.513 ± 0.045 | 0.553 ± 0.073 | 0.496 ± 0.140 (s) | 0.140 ± 0.070 (worst V-VI) |
| Questionnaire only | 0.388 ± 0.080 | 0.365 ± 0.086 | 0.426 ± 0.123 (s) | 0.149 ± 0.098 (worst III-IV) |
| Fusion concat (answer dropout) | 0.513 ± 0.050 | 0.540 ± 0.079 | 0.489 ± 0.095 (s) | 0.131 ± 0.076 (worst V-VI) |
| Fusion FiLM | 0.500 ± 0.053 | 0.549 ± 0.081 | 0.572 ± 0.109 (s) | 0.149 ± 0.053 (worst I-II) |
| Fusion gated | 0.493 ± 0.056 | 0.480 ± 0.052 | 0.453 ± 0.109 (s) | 0.124 ± 0.061 (worst V-VI) |
| DINOv2 + probe (app model) | 0.537 ± 0.076 | 0.560 ± 0.085 | 0.605 ± 0.131 (s) | 0.168 ± 0.085 (worst I-II) |
| DermLIP + probe | 0.594 ± 0.065 | 0.612 ± 0.088 | 0.636 ± 0.096 (s) | 0.157 ± 0.090 (worst I-II) |
| PanDerm-Large + probe | 0.556 ± 0.074 | 0.585 ± 0.077 | 0.580 ± 0.098 (s) | 0.155 ± 0.085 (worst I-II) |
| Photo, trained on SCIN + Fitzpatrick17k (E7) | 0.466 ± 0.074 | 0.507 ± 0.072 | 0.449 ± 0.109 (s) | 0.142 ± 0.066 (worst V-VI) |

| Model | eMST 1-3 (n=187) | eMST 4-6 (n=72) | eMST 7-10 (n=11) | gap (worst group) |
|---|---|---|---|---|
| Photo, EfficientNet-B0 | 0.534 ± 0.047 | 0.457 ± 0.069 | 0.678 ± 0.134 (s) | 0.091 ± 0.066 (worst 4-6) |
| Questionnaire only | 0.384 ± 0.053 | 0.407 ± 0.083 | 0.481 ± 0.125 (s) | 0.064 ± 0.058 (worst 1-3) |
| Fusion concat (answer dropout) | 0.534 ± 0.042 | 0.444 ± 0.068 | 0.682 ± 0.169 (s) | 0.104 ± 0.062 (worst 4-6) |
| Fusion FiLM | 0.527 ± 0.043 | 0.494 ± 0.087 | 0.702 ± 0.207 (s) | 0.064 ± 0.049 (worst 4-6) |
| Fusion gated | 0.504 ± 0.040 | 0.455 ± 0.068 | 0.630 ± 0.235 (s) | 0.078 ± 0.038 (worst 4-6) |
| DINOv2 + probe (app model) | 0.564 ± 0.074 | 0.532 ± 0.067 | 0.659 ± 0.195 (s) | 0.081 ± 0.063 (worst 4-6) |
| DermLIP + probe | 0.619 ± 0.055 | 0.577 ± 0.063 | 0.673 ± 0.220 (s) | 0.077 ± 0.051 (worst 4-6) |
| PanDerm-Large + probe | 0.590 ± 0.045 | 0.532 ± 0.085 | 0.700 ± 0.155 (s) | 0.084 ± 0.049 (worst 4-6) |
| Photo, trained on SCIN + Fitzpatrick17k (E7) | 0.482 ± 0.071 | 0.466 ± 0.110 | 0.653 ± 0.131 (s) | 0.073 ± 0.083 (worst 4-6) |

## SCIN test: balanced accuracy by tone group

| Model | eFST I-II (n=117) | eFST III-IV (n=120) | eFST V-VI (n=23) |
|---|---|---|---|
| Photo, EfficientNet-B0 | 0.577 ± 0.056 | 0.645 ± 0.059 | 0.525 ± 0.137 (s) |
| Questionnaire only | 0.431 ± 0.096 | 0.449 ± 0.143 | 0.461 ± 0.155 (s) |
| Fusion concat (answer dropout) | 0.568 ± 0.050 | 0.620 ± 0.069 | 0.534 ± 0.096 (s) |
| Fusion FiLM | 0.536 ± 0.067 | 0.623 ± 0.094 | 0.618 ± 0.092 (s) |
| Fusion gated | 0.540 ± 0.082 | 0.596 ± 0.067 | 0.510 ± 0.137 (s) |
| DINOv2 + probe (app model) | 0.607 ± 0.077 | 0.652 ± 0.082 | 0.655 ± 0.175 (s) |
| DermLIP + probe | 0.666 ± 0.057 | 0.713 ± 0.122 | 0.695 ± 0.132 (s) |
| PanDerm-Large + probe | 0.630 ± 0.080 | 0.687 ± 0.113 | 0.637 ± 0.134 (s) |
| Photo, trained on SCIN + Fitzpatrick17k (E7) | 0.465 ± 0.069 | 0.577 ± 0.103 | 0.467 ± 0.122 (s) |

| Model | eMST 1-3 (n=187) | eMST 4-6 (n=72) | eMST 7-10 (n=11) |
|---|---|---|---|
| Photo, EfficientNet-B0 | 0.607 ± 0.051 | 0.549 ± 0.112 | 0.720 ± 0.123 (s) |
| Questionnaire only | 0.430 ± 0.064 | 0.447 ± 0.101 | 0.487 ± 0.133 (s) |
| Fusion concat (answer dropout) | 0.602 ± 0.042 | 0.516 ± 0.085 | 0.721 ± 0.165 (s) |
| Fusion FiLM | 0.575 ± 0.056 | 0.544 ± 0.108 | 0.737 ± 0.182 (s) |
| Fusion gated | 0.562 ± 0.062 | 0.516 ± 0.096 | 0.617 ± 0.241 (s) |
| DINOv2 + probe (app model) | 0.634 ± 0.066 | 0.604 ± 0.123 | 0.647 ± 0.208 (s) |
| DermLIP + probe | 0.692 ± 0.059 | 0.651 ± 0.103 | 0.688 ± 0.233 (s) |
| PanDerm-Large + probe | 0.670 ± 0.064 | 0.592 ± 0.114 | 0.716 ± 0.128 (s) |
| Photo, trained on SCIN + Fitzpatrick17k (E7) | 0.489 ± 0.064 | 0.511 ± 0.114 | 0.692 ± 0.119 (s) |

## SCIN test: macro-F1 difference vs the photo-only model

| Model | eFST I-II (n=117) | eFST III-IV (n=120) | eFST V-VI (n=23) |
|---|---|---|---|
| Questionnaire only | -0.124 [-0.177, -0.075]* | -0.187 [-0.219, -0.108]* | -0.070 [-0.161, +0.007] (s) |
| Fusion concat (answer dropout) | +0.001 [-0.028, +0.028] | -0.013 [-0.047, +0.014] | -0.007 [-0.071, +0.045] (s) |
| Fusion FiLM | -0.013 [-0.047, +0.022] | -0.004 [-0.029, +0.030] | +0.076 [-0.002, +0.135] (s) |
| Fusion gated | -0.020 [-0.052, +0.014] | -0.073 [-0.095, -0.019]* | -0.043 [-0.117, +0.027] (s) |
| DINOv2 + probe (app model) | +0.024 [-0.016, +0.066] | +0.008 [-0.022, +0.082] | +0.108 [+0.022, +0.179] (s) |
| DermLIP + probe | +0.081 [+0.042, +0.127]* | +0.060 [+0.032, +0.132] | +0.139 [+0.028, +0.221] (s) |
| PanDerm-Large + probe | +0.044 [+0.003, +0.087] | +0.032 [+0.004, +0.101] | +0.084 [-0.007, +0.164] (s) |
| Photo, trained on SCIN + Fitzpatrick17k (E7) | -0.046 [-0.097, -0.005] | -0.045 [-0.082, +0.011] | -0.047 [-0.115, +0.029] (s) |

| Model | eMST 1-3 (n=187) | eMST 4-6 (n=72) | eMST 7-10 (n=11) |
|---|---|---|---|
| Questionnaire only | -0.150 [-0.192, -0.110]* | -0.050 [-0.108, +0.002] | -0.197 [-0.322, -0.080]* (s) |
| Fusion concat (answer dropout) | +0.000 [-0.023, +0.021] | -0.013 [-0.051, +0.019] | +0.004 [-0.075, +0.086] (s) |
| Fusion FiLM | -0.007 [-0.036, +0.019] | +0.037 [-0.007, +0.067] | +0.024 [-0.059, +0.109] (s) |
| Fusion gated | -0.030 [-0.062, -0.006] | -0.002 [-0.052, +0.033] | -0.048 [-0.140, +0.042] (s) |
| DINOv2 + probe (app model) | +0.030 [-0.003, +0.062] | +0.075 [+0.023, +0.119] | -0.019 [-0.103, +0.089] (s) |
| DermLIP + probe | +0.085 [+0.051, +0.121]* | +0.120 [+0.063, +0.174]* | -0.005 [-0.107, +0.117] (s) |
| PanDerm-Large + probe | +0.056 [+0.019, +0.090]* | +0.075 [+0.029, +0.130] | +0.022 [-0.083, +0.119] (s) |
| Photo, trained on SCIN + Fitzpatrick17k (E7) | -0.052 [-0.094, -0.017]* | +0.009 [-0.053, +0.049] | -0.025 [-0.093, +0.059] (s) |

## SCIN test: macro-F1 with every answer hidden minus with the answers (E2, r = 1 vs 0)

| Model | eFST I-II (n=117) | eFST III-IV (n=120) | eFST V-VI (n=23) |
|---|---|---|---|
| Fusion concat (no dropout) | -0.001 [-0.022, +0.020] | -0.008 [-0.023, +0.008] | +0.038 [-0.020, +0.064] (s) |
| Fusion concat (answer dropout) | -0.012 [-0.029, +0.008] | -0.007 [-0.026, +0.018] | -0.003 [-0.017, +0.012] (s) |
| Fusion concat (random dropout) | -0.002 [-0.012, +0.006] | -0.002 [-0.011, +0.007] | -0.019 [-0.039, -0.002] (s) |
| Fusion FiLM | +0.001 [-0.025, +0.031] | -0.009 [-0.035, +0.020] | -0.034 [-0.078, +0.014] (s) |

| Model | eMST 1-3 (n=187) | eMST 4-6 (n=72) | eMST 7-10 (n=11) |
|---|---|---|---|
| Fusion concat (no dropout) | -0.004 [-0.021, +0.014] | +0.012 [-0.006, +0.035] | -0.066 [-0.133, -0.014] (s) |
| Fusion concat (answer dropout) | -0.015 [-0.031, -0.000]* | +0.003 [-0.013, +0.024] | -0.042 [-0.089, -0.005] (s) |
| Fusion concat (random dropout) | -0.004 [-0.012, +0.003] | +0.002 [-0.007, +0.014] | -0.026 [-0.069, -0.000] (s) |
| Fusion FiLM | -0.001 [-0.023, +0.025] | -0.023 [-0.050, +0.010] | -0.089 [-0.169, -0.029] (s) |

## Fitzpatrick17k zero-shot (every in-scope image, same images for every seed): macro-F1

| Model | eFST I-II (n=2095) | eFST III-IV (n=1371) | eFST V-VI (n=433) | gap (worst group) |
|---|---|---|---|---|
| Photo, EfficientNet-B0 | 0.412 ± 0.014 | 0.371 ± 0.018 | 0.312 ± 0.023 | 0.100 ± 0.021 (worst V-VI) |
| DINOv2 + probe (app model) | 0.517 ± 0.012 | 0.524 ± 0.022 | 0.460 ± 0.035 | 0.068 ± 0.025 (worst V-VI) |

## Fitzpatrick17k zero-shot: DINOv2 + probe minus photo-only

| Model | eFST I-II (n=2095) | eFST III-IV (n=1371) | eFST V-VI (n=433) |
|---|---|---|---|
| DINOv2 + probe (app model) | +0.105 [+0.087, +0.124]* | +0.153 [+0.130, +0.177]* | +0.148 [+0.109, +0.193]* |

