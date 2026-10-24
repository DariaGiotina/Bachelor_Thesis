# E4 (Task 4.2, RQ4): calibration and abstention by skin tone

Seeds [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], SCIN test split. Temperature T fitted on validation per seed. Abstention: answer only if calibrated confidence >= tau, tau set on validation for 80% coverage. Mean ± sd over seeds; brackets: 95% interval.

## Calibration and selective prediction

| Model | T | ECE before | ECE after | NLL before | NLL after | AURC | accuracy | test coverage | selective accuracy |
|---|---|---|---|---|---|---|---|---|---|
| EfficientNet-B0 fine-tuned | 0.93 ± 0.19 | 0.079 ± 0.017 | 0.074 ± 0.020 | 0.956 ± 0.048 | 0.946 ± 0.036 | 0.345 ± 0.039 | 0.564 ± 0.026 | 0.785 ± 0.037 | 0.607 ± 0.028 |
| FiLM fusion (photo + questionnaire) | 1.01 ± 0.20 | 0.076 ± 0.024 | 0.079 ± 0.018 | 0.900 ± 0.035 | 0.896 ± 0.030 | 0.322 ± 0.031 | 0.584 ± 0.025 | 0.806 ± 0.027 | 0.616 ± 0.030 |
| DINOv2 + probe | 1.06 ± 0.31 | 0.083 ± 0.027 | 0.061 ± 0.014 | 0.884 ± 0.066 | 0.870 ± 0.058 | 0.256 ± 0.043 | 0.626 ± 0.027 | 0.798 ± 0.033 | 0.676 ± 0.025 |
| PanDerm-Large + probe | 1.44 ± 0.83 | 0.113 ± 0.062 | 0.067 ± 0.028 | 0.957 ± 0.242 | 0.867 ± 0.090 | 0.226 ± 0.024 | 0.641 ± 0.028 | 0.792 ± 0.036 | 0.699 ± 0.015 |
| DermLIP + probe | 1.15 ± 0.67 | 0.161 ± 0.115 | 0.077 ± 0.036 | 0.927 ± 0.207 | 0.806 ± 0.073 | 0.229 ± 0.042 | 0.670 ± 0.027 | 0.793 ± 0.028 | 0.720 ± 0.030 |

AURC difference vs EfficientNet-B0 fine-tuned (paired over seeds; negative = better ranking of right and wrong answers by confidence):

- FiLM fusion (photo + questionnaire): -0.023 [-0.039, -0.007], better in 8/10 seeds, t p = 0.011
- DINOv2 + probe: -0.089 [-0.116, -0.063], better in 10/10 seeds, t p = 0.000
- PanDerm-Large + probe: -0.119 [-0.144, -0.094], better in 10/10 seeds, t p = 0.000
- DermLIP + probe: -0.116 [-0.144, -0.088], better in 10/10 seeds, t p = 0.000

## Abstention rate (%), by eFST group

| Model | I-II (n=1171) | III-IV (n=1201) | V-VI (n=226) | V-VI - I-II | III-IV - I-II |
|---|---|---|---|---|---|
| EfficientNet-B0 fine-tuned | 22.0 [19.8, 24.6] | 21.5 [19.3, 23.9] | 21.2 [15.2, 26.5] | -0.8 [-7.1, 5.3] | -0.6 [-3.8, 2.8] |
| FiLM fusion (photo + questionnaire) | 20.2 [17.9, 22.5] | 20.4 [18.2, 22.6] | 14.2 [9.7, 18.8] | -6.0 [-10.8, -0.5] | +0.2 [-2.7, 3.3] |
| DINOv2 + probe | 22.5 [20.1, 25.0] | 19.2 [16.9, 21.3] | 19.0 [14.0, 24.2] | -3.5 [-9.0, 1.8] | -3.4 [-6.6, -0.1] |
| PanDerm-Large + probe | 21.2 [18.9, 23.5] | 20.1 [18.0, 22.5] | 25.2 [19.9, 30.5] | +4.0 [-1.7, 10.1] | -1.1 [-4.6, 2.3] |
| DermLIP + probe | 20.3 [18.2, 22.4] | 21.0 [18.8, 23.3] | 24.8 [19.2, 30.1] | +4.5 [-1.7, 10.2] | +0.7 [-2.5, 3.8] |

## Selective accuracy (%) on answered cases, by eFST group

| Model | I-II (n=1171) | III-IV (n=1201) | V-VI (n=226) | V-VI - I-II | III-IV - I-II |
|---|---|---|---|---|---|
| EfficientNet-B0 fine-tuned | 63.1 [59.8, 66.1] | 59.0 [55.6, 62.0] | 59.0 [51.8, 66.1] | -4.1 [-12.3, 4.1] | -4.1 [-9.0, 0.5] |
| FiLM fusion (photo + questionnaire) | 61.1 [57.8, 64.4] | 62.0 [58.8, 65.1] | 62.9 [55.8, 69.7] | +1.8 [-5.5, 9.4] | +1.0 [-3.3, 5.6] |
| DINOv2 + probe | 68.5 [65.3, 71.4] | 66.6 [63.7, 69.4] | 67.2 [59.9, 74.3] | -1.3 [-9.3, 6.6] | -1.8 [-6.1, 2.2] |
| PanDerm-Large + probe | 68.7 [65.8, 71.6] | 70.5 [67.5, 73.5] | 69.8 [62.8, 76.7] | +1.1 [-6.5, 8.9] | +1.8 [-2.3, 6.1] |
| DermLIP + probe | 71.7 [69.0, 74.5] | 72.2 [69.3, 75.1] | 69.4 [62.3, 76.4] | -2.3 [-9.8, 5.0] | +0.5 [-3.7, 4.5] |

## Abstention precision (%): declined cases that would have been wrong, by eFST group

| Model | I-II (n=1171) | III-IV (n=1201) | V-VI (n=226) | V-VI - I-II | III-IV - I-II |
|---|---|---|---|---|---|
| EfficientNet-B0 fine-tuned | 65.9 [60.2, 71.1] | 52.7 [46.8, 59.0] | 56.2 [42.5, 70.3] | -9.6 [-24.3, 5.2] | -13.2 [-21.0, -4.8] |
| FiLM fusion (photo + questionnaire) | 54.2 [48.2, 60.5] | 56.3 [50.2, 62.3] | 53.1 [35.7, 71.0] | -1.1 [-19.4, 18.3] | +2.1 [-6.8, 11.7] |
| DINOv2 + probe | 62.5 [56.7, 68.1] | 52.2 [45.7, 59.3] | 51.2 [35.1, 65.9] | -11.3 [-27.5, 4.7] | -10.3 [-18.7, -0.9] |
| PanDerm-Large + probe | 58.5 [51.8, 64.7] | 56.4 [50.2, 62.9] | 63.2 [50.8, 75.4] | +4.7 [-9.6, 17.5] | -2.0 [-10.8, 6.9] |
| DermLIP + probe | 54.2 [47.6, 60.6] | 48.8 [42.9, 54.8] | 50.0 [36.2, 63.8] | -4.2 [-19.7, 11.1] | -5.4 [-13.9, 3.2] |

## Abstention rate (%), by eMST group

| Model | 1-3 (n=1866) | 4-6 (n=723) | 7-10 (n=114) | 4-6 - 1-3 | 7-10 - 1-3 |
|---|---|---|---|---|---|
| EfficientNet-B0 fine-tuned | 21.4 [19.7, 23.4] | 21.2 [18.3, 24.0] | 22.8 [15.1, 30.9] | -0.3 [-3.8, 3.1] | +1.4 [-6.4, 9.8] |
| FiLM fusion (photo + questionnaire) | 19.8 [18.0, 21.7] | 19.4 [16.5, 22.2] | 12.3 [6.9, 18.7] | -0.5 [-3.8, 3.0] | -7.5 [-13.1, -0.9] |
| DINOv2 + probe | 19.6 [17.8, 21.4] | 22.8 [19.9, 25.8] | 13.2 [7.3, 19.6] | +3.2 [-0.3, 6.5] | -6.5 [-12.4, 0.6] |
| PanDerm-Large + probe | 20.6 [18.9, 22.5] | 21.7 [18.9, 25.1] | 18.4 [11.6, 25.6] | +1.1 [-2.2, 4.8] | -2.2 [-9.5, 5.3] |
| DermLIP + probe | 19.8 [18.1, 21.6] | 22.0 [19.0, 25.2] | 28.1 [19.8, 36.3] | +2.2 [-1.2, 5.5] | +8.2 [-0.9, 16.6] |

## Selective accuracy (%) on answered cases, by eMST group

| Model | 1-3 (n=1866) | 4-6 (n=723) | 7-10 (n=114) | 4-6 - 1-3 | 7-10 - 1-3 |
|---|---|---|---|---|---|
| EfficientNet-B0 fine-tuned | 62.6 [59.9, 65.0] | 53.7 [49.6, 58.0] | 73.9 [64.0, 82.8] | -8.9 [-13.9, -4.1] | +11.2 [1.3, 21.2] |
| FiLM fusion (photo + questionnaire) | 63.2 [60.8, 65.7] | 55.1 [51.2, 59.2] | 76.0 [67.3, 84.2] | -8.1 [-12.6, -3.3] | +12.8 [3.4, 21.5] |
| DINOv2 + probe | 68.9 [66.6, 71.1] | 64.0 [59.9, 67.8] | 71.7 [62.6, 81.0] | -4.9 [-9.3, -0.4] | +2.9 [-7.0, 12.1] |
| PanDerm-Large + probe | 70.9 [68.5, 73.3] | 66.3 [62.6, 70.0] | 77.4 [68.3, 85.9] | -4.6 [-9.2, -0.2] | +6.5 [-2.9, 15.2] |
| DermLIP + probe | 73.4 [71.2, 75.5] | 67.0 [63.2, 70.8] | 80.5 [72.1, 89.0] | -6.4 [-10.8, -1.7] | +7.1 [-1.6, 16.1] |

## Abstention precision (%): declined cases that would have been wrong, by eMST group

| Model | 1-3 (n=1866) | 4-6 (n=723) | 7-10 (n=114) | 4-6 - 1-3 | 7-10 - 1-3 |
|---|---|---|---|---|---|
| EfficientNet-B0 fine-tuned | 61.3 [56.7, 65.8] | 56.9 [48.5, 64.7] | 42.3 [22.7, 61.9] | -4.4 [-13.6, 4.6] | -18.9 [-39.1, 1.2] |
| FiLM fusion (photo + questionnaire) | 55.9 [51.0, 61.1] | 52.1 [43.7, 60.8] | 50.0 [20.0, 80.0] | -3.8 [-13.5, 6.1] | -5.9 [-36.7, 24.9] |
| DINOv2 + probe | 59.0 [54.2, 63.7] | 55.8 [47.9, 63.1] | 40.0 [15.8, 66.7] | -3.3 [-12.4, 5.8] | -19.0 [-43.5, 8.4] |
| PanDerm-Large + probe | 57.4 [52.5, 62.0] | 59.9 [52.8, 68.1] | 57.1 [35.3, 80.0] | +2.5 [-6.0, 12.8] | -0.3 [-22.4, 22.4] |
| DermLIP + probe | 51.1 [45.8, 56.0] | 53.5 [45.2, 61.1] | 56.2 [38.1, 73.3] | +2.4 [-7.5, 11.6] | +5.2 [-13.2, 23.6] |

n = test cases pooled over the seeds (SCIN: different test split per seed; intervals from a case bootstrap within each seed). Differences are paired (same bootstrap resamples).

## External sets (zero-shot; each model's SCIN T and tau)

Every seed's model scores the same external images, so the intervals resample whole images (cluster bootstrap). In scope: diagnoses that map to our four categories. Out of scope: every other diagnosis (the model was never trained on them, so abstaining is the right answer). Malignant (DDI only): biopsy-confirmed malignant lesions; coverage = share answered with a confident benign label, without the advice to see a professional (lower is safer).

| Set | Model | Images | Metric | ALL | I-II | III-IV | V-VI | V-VI - I-II | III-IV - I-II |
|---|---|---|---|---|---|---|---|---|---|
| fitzpatrick17k | EfficientNet-B0 fine-tuned | in scope, 4012 | accuracy | 42.9 [41.7, 44.1] | 43.4 [41.7, 45.1] | 43.4 [41.5, 45.5] | 39.4 [36.2, 42.5] | -4.1 [-7.5, -0.5] | -0.0 [-2.6, 2.7] |
| fitzpatrick17k | EfficientNet-B0 fine-tuned | in scope, 4012 | abstention_rate | 30.6 [29.7, 31.5] | 27.5 [26.3, 28.8] | 31.9 [30.5, 33.4] | 38.8 [36.0, 41.4] | +11.2 [8.0, 14.1] | +4.4 [2.5, 6.4] |
| fitzpatrick17k | EfficientNet-B0 fine-tuned | in scope, 4012 | selective_accuracy | 46.0 [44.6, 47.6] | 46.6 [44.7, 48.7] | 46.8 [44.4, 49.3] | 41.6 [37.4, 45.7] | -5.0 [-9.5, -0.4] | +0.2 [-3.0, 3.5] |
| fitzpatrick17k | DINOv2 + probe | in scope, 4012 | accuracy | 53.8 [52.5, 55.1] | 52.9 [51.2, 54.6] | 55.7 [53.5, 57.8] | 55.4 [51.8, 59.0] | +2.5 [-1.6, 6.5] | +2.8 [0.2, 5.6] |
| fitzpatrick17k | DINOv2 + probe | in scope, 4012 | abstention_rate | 16.9 [16.3, 17.6] | 16.6 [15.7, 17.5] | 18.2 [17.0, 19.4] | 14.0 [12.3, 15.8] | -2.6 [-4.6, -0.5] | +1.6 [-0.0, 3.1] |
| fitzpatrick17k | DINOv2 + probe | in scope, 4012 | selective_accuracy | 56.9 [55.5, 58.3] | 55.6 [53.7, 57.6] | 59.2 [56.7, 61.7] | 58.4 [54.5, 62.1] | +2.8 [-1.6, 6.9] | +3.6 [0.6, 6.6] |
| fitzpatrick17k | EfficientNet-B0 fine-tuned | out of scope, 12559 | abstention_rate | 31.6 [31.1, 32.1] | 29.9 [29.2, 30.6] | 30.6 [29.8, 31.4] | 36.0 [34.7, 37.4] | +6.1 [4.6, 7.7] | +0.7 [-0.4, 1.8] |
| fitzpatrick17k | DINOv2 + probe | out of scope, 12559 | abstention_rate | 18.6 [18.2, 18.9] | 19.7 [19.1, 20.3] | 18.5 [17.9, 19.1] | 15.4 [14.4, 16.4] | -4.3 [-5.4, -3.1] | -1.2 [-2.0, -0.3] |
| ddi | EfficientNet-B0 fine-tuned | in scope, 178 | accuracy | 45.6 [41.1, 49.8] | 39.6 [32.9, 46.5] | 50.2 [43.0, 58.0] | 49.4 [40.7, 58.7] | +9.8 [-1.4, 21.2] | +10.6 [0.5, 21.0] |
| ddi | EfficientNet-B0 fine-tuned | in scope, 178 | abstention_rate | 47.9 [43.8, 52.3] | 45.9 [38.7, 53.2] | 51.9 [43.7, 59.3] | 46.2 [37.6, 55.0] | +0.4 [-11.2, 12.3] | +6.0 [-4.9, 16.2] |
| ddi | EfficientNet-B0 fine-tuned | in scope, 178 | selective_accuracy | 49.0 [42.1, 54.9] | 38.2 [27.8, 48.5] | 56.9 [45.6, 68.6] | 57.0 [44.2, 69.1] | +18.7 [1.6, 34.4] | +18.7 [3.2, 34.9] |
| ddi | DINOv2 + probe | in scope, 178 | accuracy | 25.6 [20.1, 30.9] | 24.7 [16.8, 32.9] | 20.2 [12.8, 28.4] | 33.3 [22.0, 45.1] | +8.7 [-6.0, 22.6] | -4.5 [-16.3, 6.8] |
| ddi | DINOv2 + probe | in scope, 178 | abstention_rate | 21.3 [17.8, 24.5] | 28.8 [22.9, 34.9] | 20.9 [15.2, 25.9] | 10.4 [5.9, 15.8] | -18.4 [-25.8, -10.6] | -7.9 [-16.2, 0.2] |
| ddi | DINOv2 + probe | in scope, 178 | selective_accuracy | 25.5 [19.4, 31.9] | 23.8 [14.3, 33.9] | 19.7 [11.4, 29.2] | 33.5 [21.6, 46.1] | +9.6 [-6.0, 25.0] | -4.1 [-17.3, 9.3] |
| ddi | EfficientNet-B0 fine-tuned | out of scope, 478 | abstention_rate | 45.5 [42.7, 48.3] | 44.4 [39.3, 49.2] | 50.2 [45.9, 55.1] | 41.1 [36.5, 45.9] | -3.2 [-9.7, 3.9] | +5.8 [-0.7, 13.1] |
| ddi | DINOv2 + probe | out of scope, 478 | abstention_rate | 21.4 [19.3, 23.6] | 25.2 [20.9, 30.1] | 22.8 [19.3, 26.8] | 16.6 [13.3, 20.1] | -8.6 [-14.3, -3.1] | -2.4 [-8.3, 3.7] |
| ddi | EfficientNet-B0 fine-tuned | malignant, 171 | coverage | 55.0 [50.4, 59.3] | 52.7 [44.3, 61.3] | 46.8 [40.2, 53.4] | 70.0 [61.6, 77.5] | +17.3 [4.7, 28.4] | -5.9 [-16.5, 4.8] |
| ddi | DINOv2 + probe | malignant, 171 | coverage | 79.5 [75.7, 82.9] | 79.0 [72.6, 85.1] | 74.9 [68.8, 80.7] | 87.3 [80.8, 92.7] | +8.3 [-0.4, 17.1] | -4.1 [-12.8, 4.5] |
