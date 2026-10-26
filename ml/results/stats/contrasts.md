# Task 4.4: main contrasts, one test procedure

Difference a - b per split seed (10 seeds). Interval: 95% t interval over seeds; case bootstrap: the experiment runner's interval (resampled test cases), where it stored this contrast. p: paired t-test and Wilcoxon over seeds; Holm within the family and over all contrasts. checked = the runner's stored mean and t-test p agree with this recomputation (mean within 1e-4, p within 0.005; stored per-seed values are rounded).

## RQ1 questionnaire (E1)

| Contrast | metric | mean diff | 95% t interval | case bootstrap | better seeds | t p | Wilcoxon p | Holm (family) | Holm (all) | checked |
|---|---|---|---|---|---|---|---|---|---|---|
| fusion concat - photo | macro-F1 | -0.005 | [-0.029, +0.020] | [-0.024, +0.014] | 6/10 | 0.667 | 0.770 | 1.000 | 1.000 | yes |
| fusion FiLM - photo | macro-F1 | +0.000 | [-0.021, +0.022] | [-0.023, +0.023] | 5/10 | 0.971 | 0.846 | 1.000 | 1.000 | yes |
| fusion gated - photo | macro-F1 | -0.030 | [-0.062, +0.003] | [-0.053, -0.007] | 2/10 | 0.071 | 0.037 | 0.354 | 1.000 | yes |
| fusion concat, no dropout - photo | macro-F1 | -0.014 | [-0.032, +0.004] | [-0.035, +0.006] | 3/10 | 0.116 | 0.105 | 0.354 | 1.000 | yes |
| ensemble photo + questionnaire - photo | macro-F1 | -0.021 | [-0.045, +0.003] | [-0.047, +0.003] | 3/10 | 0.084 | 0.148 | 0.354 | 1.000 | yes |
| questionnaire only - photo | macro-F1 | -0.138 | [-0.168, -0.109] | - | 0/10 | 0.000 | 0.002 | 0.000 | 0.000 | - |

## RQ2 missing answers (E2)

| Contrast | metric | mean diff | 95% t interval | case bootstrap | better seeds | t p | Wilcoxon p | Holm (family) | Holm (all) | checked |
|---|---|---|---|---|---|---|---|---|---|---|
| fixed answer dropout - no dropout, 0% hidden | macro-F1 | +0.009 | [-0.010, +0.028] | [-0.006, +0.025] | 6/10 | 0.312 | 0.492 | 1.000 | 1.000 | yes |
| fixed answer dropout - no dropout, 100% hidden | macro-F1 | +0.000 | [-0.016, +0.016] | [-0.015, +0.017] | 3/10 | 0.982 | 0.695 | 1.000 | 1.000 | yes |
| random answer dropout - no dropout, 0% hidden | macro-F1 | +0.005 | [-0.008, +0.018] | [-0.010, +0.021] | 7/10 | 0.388 | 0.322 | 1.000 | 1.000 | yes |
| random answer dropout - no dropout, 100% hidden | macro-F1 | +0.003 | [-0.016, +0.021] | [-0.015, +0.020] | 4/10 | 0.758 | 1.000 | 1.000 | 1.000 | yes |
| concat nodrop: 100% - 0% hidden | macro-F1 | -0.001 | [-0.014, +0.013] | [-0.016, +0.015] | 3/10 | 0.899 | 0.492 | 1.000 | 1.000 | yes |
| concat fixed: 100% - 0% hidden | macro-F1 | -0.010 | [-0.022, +0.003] | [-0.022, +0.003] | 3/10 | 0.113 | 0.105 | 0.790 | 1.000 | yes |
| concat randdrop: 100% - 0% hidden | macro-F1 | -0.003 | [-0.012, +0.005] | [-0.009, +0.003] | 4/10 | 0.411 | 0.922 | 1.000 | 1.000 | yes |

## E5 frozen encoders

| Contrast | metric | mean diff | 95% t interval | case bootstrap | better seeds | t p | Wilcoxon p | Holm (family) | Holm (all) | checked |
|---|---|---|---|---|---|---|---|---|---|---|
| EfficientNet-B0 ImageNet probe - fine-tuned photo | macro-F1 | -0.072 | [-0.098, -0.045] | [-0.099, -0.044] | 0/10 | 0.000 | 0.002 | 0.001 | 0.003 | yes |
| ViT-B/16 ImageNet-21k probe - fine-tuned photo | macro-F1 | -0.069 | [-0.099, -0.040] | [-0.097, -0.039] | 0/10 | 0.000 | 0.002 | 0.002 | 0.010 | yes |
| DINOv2 probe - fine-tuned photo | macro-F1 | +0.032 | [-0.018, +0.082] | [+0.005, +0.061] | 7/10 | 0.185 | 0.131 | 0.185 | 1.000 | yes |
| PanDerm-Base probe - fine-tuned photo | macro-F1 | +0.034 | [-0.003, +0.071] | [+0.003, +0.066] | 8/10 | 0.069 | 0.064 | 0.138 | 1.000 | yes |
| PanDerm-Large probe - fine-tuned photo | macro-F1 | +0.047 | [+0.008, +0.086] | [+0.017, +0.078] | 7/10 | 0.022 | 0.037 | 0.067 | 0.381 | yes |
| DermLIP probe - fine-tuned photo | macro-F1 | +0.084 | [+0.055, +0.113] | [+0.052, +0.114] | 10/10 | 0.000 | 0.002 | 0.001 | 0.003 | yes |

## E7 extra training data

| Contrast | metric | mean diff | 95% t interval | case bootstrap | better seeds | t p | Wilcoxon p | Holm (family) | Holm (all) | checked |
|---|---|---|---|---|---|---|---|---|---|---|
| pooled SCIN + Fitzpatrick17k - photo, SCIN test | macro-F1 | -0.035 | [-0.061, -0.008] | [-0.071, -0.002] | 2/10 | 0.016 | 0.020 | 0.032 | 0.289 | yes |
| Fitzpatrick17k then SCIN - photo, SCIN test | macro-F1 | -0.024 | [-0.050, +0.003] | [-0.049, +0.001] | 3/10 | 0.073 | 0.064 | 0.073 | 1.000 | yes |

## RQ4 confidence ranking (E4)

| Contrast | metric | mean diff | 95% t interval | case bootstrap | better seeds | t p | Wilcoxon p | Holm (family) | Holm (all) | checked |
|---|---|---|---|---|---|---|---|---|---|---|
| FiLM fusion - photo | AURC reduction | +0.023 | [+0.007, +0.039] | - | 8/10 | 0.011 | 0.020 | 0.011 | 0.205 | - |
| DINOv2 probe - photo | AURC reduction | +0.089 | [+0.063, +0.116] | - | 10/10 | 0.000 | 0.002 | 0.000 | 0.001 | - |
| PanDerm-Large probe - photo | AURC reduction | +0.119 | [+0.094, +0.144] | - | 10/10 | 0.000 | 0.002 | 0.000 | 0.000 | - |
| DermLIP probe - photo | AURC reduction | +0.116 | [+0.088, +0.144] | - | 10/10 | 0.000 | 0.002 | 0.000 | 0.000 | - |

## Out-of-scope detector (4.2b)

| Contrast | metric | mean diff | 95% t interval | case bootstrap | better seeds | t p | Wilcoxon p | Holm (family) | Holm (all) | checked |
|---|---|---|---|---|---|---|---|---|---|---|
| kNN - max probability, SCIN other conditions | AUROC | +0.006 | [-0.016, +0.029] | - | 6/10 | 0.535 | 0.625 | 0.535 | 1.000 | - |
| Mahalanobis - kNN, SCIN other conditions | AUROC | +0.021 | [+0.017, +0.025] | - | 10/10 | 0.000 | 0.002 | 0.000 | 0.000 | - |
| kNN - max probability, DDI malignant | AUROC | +0.295 | [+0.252, +0.338] | - | 10/10 | 0.000 | 0.002 | 0.000 | 0.000 | - |
| Mahalanobis - kNN, DDI malignant | AUROC | +0.058 | [+0.054, +0.062] | - | 10/10 | 0.000 | 0.002 | 0.000 | 0.000 | - |
| kNN - max probability, Fitzpatrick17k out of scope | AUROC | +0.227 | [+0.199, +0.256] | - | 10/10 | 0.000 | 0.002 | 0.000 | 0.000 | - |
| Mahalanobis - kNN, Fitzpatrick17k out of scope | AUROC | +0.047 | [+0.045, +0.050] | - | 10/10 | 0.000 | 0.002 | 0.000 | 0.000 | - |
