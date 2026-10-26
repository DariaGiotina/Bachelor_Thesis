# Task 4.4: every main contrast, one procedure

| family | contrast | metric | mean diff | 95% t interval | better seeds | Holm p (family) | Holm p (all) |
|---|---|---|---|---|---|---|---|
| RQ1 questionnaire (E1) | fusion concat - photo | macro-F1 | -0.005 | [-0.029, +0.020] | 6/10 | 1.000 | 1.000 |
| RQ1 questionnaire (E1) | fusion FiLM - photo | macro-F1 | +0.000 | [-0.021, +0.022] | 5/10 | 1.000 | 1.000 |
| RQ1 questionnaire (E1) | fusion gated - photo | macro-F1 | -0.030 | [-0.062, +0.003] | 2/10 | 0.354 | 1.000 |
| RQ1 questionnaire (E1) | fusion concat, no dropout - photo | macro-F1 | -0.014 | [-0.032, +0.004] | 3/10 | 0.354 | 1.000 |
| RQ1 questionnaire (E1) | ensemble photo + questionnaire - photo | macro-F1 | -0.021 | [-0.045, +0.003] | 3/10 | 0.354 | 1.000 |
| RQ1 questionnaire (E1) | questionnaire only - photo | macro-F1 | -0.138 | [-0.168, -0.109] | 0/10 | 0.000 | 0.000 |
| RQ2 missing answers (E2) | fixed answer dropout - no dropout, 0% hidden | macro-F1 | +0.009 | [-0.010, +0.028] | 6/10 | 1.000 | 1.000 |
| RQ2 missing answers (E2) | fixed answer dropout - no dropout, 100% hidden | macro-F1 | +0.000 | [-0.016, +0.016] | 3/10 | 1.000 | 1.000 |
| RQ2 missing answers (E2) | random answer dropout - no dropout, 0% hidden | macro-F1 | +0.005 | [-0.008, +0.018] | 7/10 | 1.000 | 1.000 |
| RQ2 missing answers (E2) | random answer dropout - no dropout, 100% hidden | macro-F1 | +0.003 | [-0.016, +0.021] | 4/10 | 1.000 | 1.000 |
| RQ2 missing answers (E2) | concat nodrop: 100% - 0% hidden | macro-F1 | -0.001 | [-0.014, +0.013] | 3/10 | 1.000 | 1.000 |
| RQ2 missing answers (E2) | concat fixed: 100% - 0% hidden | macro-F1 | -0.010 | [-0.022, +0.003] | 3/10 | 0.790 | 1.000 |
| RQ2 missing answers (E2) | concat randdrop: 100% - 0% hidden | macro-F1 | -0.003 | [-0.012, +0.005] | 4/10 | 1.000 | 1.000 |
| E5 frozen encoders | EfficientNet-B0 ImageNet probe - fine-tuned photo | macro-F1 | -0.072 | [-0.098, -0.045] | 0/10 | 0.001 | 0.003 |
| E5 frozen encoders | ViT-B/16 ImageNet-21k probe - fine-tuned photo | macro-F1 | -0.069 | [-0.099, -0.040] | 0/10 | 0.002 | 0.010 |
| E5 frozen encoders | DINOv2 probe - fine-tuned photo | macro-F1 | +0.032 | [-0.018, +0.082] | 7/10 | 0.185 | 1.000 |
| E5 frozen encoders | PanDerm-Base probe - fine-tuned photo | macro-F1 | +0.034 | [-0.003, +0.071] | 8/10 | 0.138 | 1.000 |
| E5 frozen encoders | PanDerm-Large probe - fine-tuned photo | macro-F1 | +0.047 | [+0.008, +0.086] | 7/10 | 0.067 | 0.381 |
| E5 frozen encoders | DermLIP probe - fine-tuned photo | macro-F1 | +0.084 | [+0.055, +0.113] | 10/10 | 0.001 | 0.003 |
| E7 extra training data | pooled SCIN + Fitzpatrick17k - photo, SCIN test | macro-F1 | -0.035 | [-0.061, -0.008] | 2/10 | 0.032 | 0.289 |
| E7 extra training data | Fitzpatrick17k then SCIN - photo, SCIN test | macro-F1 | -0.024 | [-0.050, +0.003] | 3/10 | 0.073 | 1.000 |
| RQ4 confidence ranking (E4) | FiLM fusion - photo | AURC reduction | +0.023 | [+0.007, +0.039] | 8/10 | 0.011 | 0.205 |
| RQ4 confidence ranking (E4) | DINOv2 probe - photo | AURC reduction | +0.089 | [+0.063, +0.116] | 10/10 | 0.000 | 0.001 |
| RQ4 confidence ranking (E4) | PanDerm-Large probe - photo | AURC reduction | +0.119 | [+0.094, +0.144] | 10/10 | 0.000 | 0.000 |
| RQ4 confidence ranking (E4) | DermLIP probe - photo | AURC reduction | +0.116 | [+0.088, +0.144] | 10/10 | 0.000 | 0.000 |
| Out-of-scope detector (4.2b) | kNN - max probability, SCIN other conditions | AUROC | +0.006 | [-0.016, +0.029] | 6/10 | 0.535 | 1.000 |
| Out-of-scope detector (4.2b) | Mahalanobis - kNN, SCIN other conditions | AUROC | +0.021 | [+0.017, +0.025] | 10/10 | 0.000 | 0.000 |
| Out-of-scope detector (4.2b) | kNN - max probability, DDI malignant | AUROC | +0.295 | [+0.252, +0.338] | 10/10 | 0.000 | 0.000 |
| Out-of-scope detector (4.2b) | Mahalanobis - kNN, DDI malignant | AUROC | +0.058 | [+0.054, +0.062] | 10/10 | 0.000 | 0.000 |
| Out-of-scope detector (4.2b) | kNN - max probability, Fitzpatrick17k out of scope | AUROC | +0.227 | [+0.199, +0.256] | 10/10 | 0.000 | 0.000 |
| Out-of-scope detector (4.2b) | Mahalanobis - kNN, Fitzpatrick17k out of scope | AUROC | +0.047 | [+0.045, +0.050] | 10/10 | 0.000 | 0.000 |
