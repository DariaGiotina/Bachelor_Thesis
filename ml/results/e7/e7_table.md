# E7: adding Fitzpatrick17k training images (seeds [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])

Backbone efficientnet_b0, class-weighted loss, staged fine-tuning, early stopping on SCIN val. image_only = E1 photo-only model (SCIN only; on fitz_test it is zero-shot). Each cell: mean ± sd over seeds [95% seed-stratified case-bootstrap CI].

## SCIN test split

| Arm | Macro-F1 | Balanced accuracy | ECE |
|---|---|---|---|
| image_only | 0.519 ± 0.040 [0.485, 0.541] | 0.610 ± 0.038 [0.580, 0.639] | 0.079 ± 0.017 [0.066, 0.093] |
| fitz_pooled | 0.484 ± 0.071 [0.443, 0.511] | 0.499 ± 0.070 [0.461, 0.538] | 0.081 ± 0.019 [0.068, 0.095] |
| fitz_pretrain | 0.496 ± 0.051 [0.461, 0.518] | 0.576 ± 0.065 [0.542, 0.608] | 0.077 ± 0.011 [0.064, 0.092] |

Paired macro-F1 difference vs image_only (mean [95% CI], seeds better, t-test p, Wilcoxon p):

- fitz_pooled - image_only: -0.035 [-0.071, -0.002], 2/10 seeds, t p = 0.016, Wilcoxon p = 0.020
- fitz_pretrain - image_only: -0.024 [-0.049, +0.001], 3/10 seeds, t p = 0.073, Wilcoxon p = 0.064

### By skin tone (macro-F1) and by category (F1)

Mean ± sd over seeds. Mean test cases per seed: eFST I-II 117, eFST III-IV 120, eFST V-VI 23, eMST 1-3 187, eMST 4-6 72, eMST 7-10 11, acne 22, eczema_dermatitis 159, redness_rosacea 6, normal_other 84.

| Arm | eFST I-II | eFST III-IV | eFST V-VI | eMST 1-3 | eMST 4-6 | eMST 7-10 | acne | eczema_dermatitis | redness_rosacea | normal_other |
|---|---|---|---|---|---|---|---|---|---|---|
| image_only | 0.513 ± 0.045 | 0.553 ± 0.073 | 0.496 ± 0.140 | 0.534 ± 0.047 | 0.457 ± 0.069 | 0.678 ± 0.134 | 0.320 ± 0.064 | 0.689 ± 0.018 | 0.633 ± 0.101 | 0.435 ± 0.043 |
| fitz_pooled | 0.466 ± 0.074 | 0.507 ± 0.072 | 0.449 ± 0.109 | 0.482 ± 0.071 | 0.466 ± 0.110 | 0.653 ± 0.131 | 0.263 ± 0.099 | 0.731 ± 0.027 | 0.526 ± 0.160 | 0.418 ± 0.054 |
| fitz_pretrain | 0.491 ± 0.048 | 0.496 ± 0.083 | 0.471 ± 0.093 | 0.503 ± 0.046 | 0.465 ± 0.104 | 0.666 ± 0.132 | 0.296 ± 0.065 | 0.691 ± 0.038 | 0.564 ± 0.133 | 0.432 ± 0.050 |

Difference vs image_only: mean [95% seed-stratified paired bootstrap CI], seeds better; Holm-adjusted p shown when < 0.05 (family = all groups and categories of one comparison).

| Arm | eFST I-II | eFST III-IV | eFST V-VI | eMST 1-3 | eMST 4-6 | eMST 7-10 | acne | eczema_dermatitis | redness_rosacea | normal_other |
|---|---|---|---|---|---|---|---|---|---|---|
| fitz_pooled | -0.046 [-0.095, -0.005] 2/10 | -0.045 [-0.085, +0.013] 4/10 | -0.047 [-0.115, +0.034] 4/10 | -0.052 [-0.093, -0.017] 1/10 **p=0.035** | +0.009 [-0.051, +0.052] 6/10 | -0.025 [-0.093, +0.056] 3/10 | -0.057 [-0.109, -0.009] 2/10 | +0.042 [+0.025, +0.059] 9/10 **p=0.035** | -0.107 [-0.221, -0.010] 0/10 **p=0.035** | -0.017 [-0.050, +0.018] 3/10 |
| fitz_pretrain | -0.021 [-0.059, +0.012] 3/10 | -0.057 [-0.078, -0.004] 3/10 | -0.025 [-0.086, +0.037] 4/10 | -0.031 [-0.060, -0.004] 2/10 | +0.008 [-0.039, +0.043] 7/10 | -0.012 [-0.076, +0.052] 4/10 | -0.024 [-0.059, +0.012] 3/10 | +0.002 [-0.015, +0.018] 5/10 | -0.069 [-0.146, +0.004] 2/10 | -0.003 [-0.033, +0.026] 6/10 |


## Fitzpatrick17k held-out test fold

| Arm | Macro-F1 | Balanced accuracy | ECE |
|---|---|---|---|
| image_only | 0.410 ± 0.022 [0.398, 0.422] | 0.445 ± 0.021 [0.432, 0.459] | 0.087 ± 0.033 [0.078, 0.097] |
| fitz_pooled | 0.626 ± 0.062 [0.614, 0.637] | 0.688 ± 0.044 [0.677, 0.699] | 0.054 ± 0.011 [0.046, 0.062] |
| fitz_pretrain | 0.464 ± 0.049 [0.450, 0.475] | 0.519 ± 0.071 [0.505, 0.533] | 0.101 ± 0.028 [0.092, 0.111] |

Paired macro-F1 difference vs image_only (mean [95% CI], seeds better, t-test p, Wilcoxon p):

- fitz_pooled - image_only: +0.216 [+0.202, +0.231], 10/10 seeds, t p = 0.000, Wilcoxon p = 0.002
- fitz_pretrain - image_only: +0.053 [+0.042, +0.065], 9/10 seeds, t p = 0.008, Wilcoxon p = 0.010

### By skin tone (macro-F1) and by category (F1)

Mean ± sd over seeds. Mean test cases per seed: eFST I-II 442, eFST III-IV 260, eFST V-VI 84, acne 172, eczema_dermatitis 202, redness_rosacea 51, normal_other 379.

| Arm | eFST I-II | eFST III-IV | eFST V-VI | acne | eczema_dermatitis | redness_rosacea | normal_other |
|---|---|---|---|---|---|---|---|
| image_only | 0.429 ± 0.025 | 0.380 ± 0.036 | 0.353 ± 0.048 | 0.530 ± 0.051 | 0.411 ± 0.031 | 0.232 ± 0.054 | 0.467 ± 0.042 |
| fitz_pooled | 0.633 ± 0.061 | 0.615 ± 0.069 | 0.606 ± 0.094 | 0.734 ± 0.058 | 0.469 ± 0.076 | 0.617 ± 0.073 | 0.685 ± 0.059 |
| fitz_pretrain | 0.480 ± 0.042 | 0.431 ± 0.066 | 0.422 ± 0.076 | 0.578 ± 0.053 | 0.449 ± 0.035 | 0.333 ± 0.093 | 0.495 ± 0.065 |

Difference vs image_only: mean [95% seed-stratified paired bootstrap CI], seeds better; Holm-adjusted p shown when < 0.05 (family = all groups and categories of one comparison).

| Arm | eFST I-II | eFST III-IV | eFST V-VI | acne | eczema_dermatitis | redness_rosacea | normal_other |
|---|---|---|---|---|---|---|---|
| fitz_pooled | +0.204 [+0.186, +0.221] 10/10 **p=0.000** | +0.234 [+0.208, +0.258] 10/10 **p=0.000** | +0.253 [+0.193, +0.289] 10/10 **p=0.000** | +0.204 [+0.186, +0.221] 10/10 **p=0.000** | +0.058 [+0.038, +0.078] 8/10 **p=0.017** | +0.384 [+0.345, +0.421] 10/10 **p=0.000** | +0.219 [+0.202, +0.235] 10/10 **p=0.000** |
| fitz_pretrain | +0.051 [+0.035, +0.066] 9/10 **p=0.045** | +0.050 [+0.030, +0.070] 8/10 | +0.069 [+0.032, +0.103] 10/10 **p=0.018** | +0.048 [+0.031, +0.065] 7/10 | +0.037 [+0.023, +0.052] 10/10 **p=0.013** | +0.100 [+0.070, +0.128] 9/10 **p=0.034** | +0.028 [+0.012, +0.045] 7/10 |

