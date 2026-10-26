# Task 4.2b: out-of-scope detector for the DINOv2 app model

Seeds [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]. Detectors fitted on each seed's SCIN train features (frozen DINOv2 ViT-B/14), threshold = 95th percentile on the seed's validation cases. Primary detector: kNN, k = 10 (fixed in advance). Mean ± sd over seeds; brackets: 95% bootstrap interval (SCIN test: cases within seeds; other sets: whole images).

Images per set: SCIN test (in scope) 270, SCIN, other conditions 463, Fitzpatrick17k in scope 4012, Fitzpatrick17k out of scope 12559, DDI out of scope 478, DDI malignant 171.

## Separation from the SCIN test cases (AUROC; 0.5 = chance, 1 = perfect)

| Set | msp | mahalanobis | knn |
|---|---|---|---|
| SCIN, other conditions | 0.498 ± 0.019 | 0.525 ± 0.020 | 0.504 ± 0.017 |
| Fitzpatrick17k in scope | 0.464 ± 0.030 | 0.755 ± 0.016 | 0.719 ± 0.016 |
| Fitzpatrick17k out of scope | 0.497 ± 0.033 | 0.772 ± 0.015 | 0.724 ± 0.015 |
| DDI out of scope | 0.509 ± 0.062 | 0.887 ± 0.010 | 0.832 ± 0.015 |
| DDI malignant | 0.501 ± 0.052 | 0.855 ± 0.012 | 0.797 ± 0.015 |

## Share flagged at the validation threshold (%)

| Set | msp | mahalanobis | knn |
|---|---|---|---|
| SCIN test (in scope), false alarms | 5.1 ± 1.8 | 4.9 ± 2.2 | 5.1 ± 2.5 |
| SCIN, other conditions | 4.4 ± 1.5 | 5.2 ± 1.2 | 4.6 ± 1.1 |
| Fitzpatrick17k in scope | 4.3 ± 1.5 | 23.7 ± 3.9 | 17.4 ± 3.7 |
| Fitzpatrick17k out of scope | 4.9 ± 1.8 | 26.1 ± 4.1 | 18.9 ± 3.3 |
| DDI out of scope | 5.8 ± 2.9 | 56.7 ± 4.8 | 28.4 ± 5.8 |
| DDI malignant | 5.8 ± 2.8 | 50.3 ± 3.6 | 23.6 ± 5.2 |

## kNN sensitivity to k (AUROC, mean over seeds; k = 10 was fixed before the run)

| Set | k = 1 | k = 5 | k = 10 | k = 20 | k = 50 |
|---|---|---|---|---|---|
| SCIN, other conditions | 0.517 | 0.507 | 0.504 | 0.503 | 0.502 |
| Fitzpatrick17k in scope | 0.704 | 0.716 | 0.719 | 0.723 | 0.723 |
| Fitzpatrick17k out of scope | 0.729 | 0.728 | 0.724 | 0.721 | 0.717 |
| DDI out of scope | 0.858 | 0.842 | 0.832 | 0.820 | 0.803 |
| DDI malignant | 0.825 | 0.807 | 0.797 | 0.785 | 0.768 |

## Answered with a label (%), by eFST group

Flagged by kNN: share NOT flagged. Confidence only: the E4 rule (calibrated confidence >= tau). Combined: confident and not flagged. On in-scope sets a higher share is better; on out-of-scope and malignant sets a lower share is safer.

| Set | Rule | ALL | I-II | III-IV | V-VI | V-VI - I-II |
|---|---|---|---|---|---|---|
| SCIN test (in scope) | not flagged by kNN | 94.9 [94.0, 95.7] | 96.4 [95.2, 97.4] | 94.0 [92.8, 95.3] | 91.2 [87.2, 94.7] | -5.3 [-9.3, -1.4] |
| SCIN test (in scope) | confidence only | 79.8 [78.4, 81.3] | 77.5 [75.0, 79.9] | 80.8 [78.7, 83.1] | 81.0 [75.8, 86.0] | +3.5 [-1.8, 9.0] |
| SCIN test (in scope) | combined | 75.9 [74.3, 77.5] | 74.6 [72.1, 77.2] | 76.4 [73.9, 78.8] | 74.3 [68.3, 80.1] | -0.3 [-6.9, 5.5] |
| SCIN, other conditions | not flagged by kNN | 95.4 [93.5, 97.1] | 95.8 [92.5, 98.7] | 95.8 [93.2, 98.0] | 95.0 [88.0, 99.8] | -0.8 [-7.7, 5.5] |
| SCIN, other conditions | confidence only | 80.3 [77.9, 82.7] | 81.2 [77.4, 85.0] | 78.6 [74.8, 82.5] | 82.3 [74.7, 88.7] | +1.1 [-7.5, 8.7] |
| SCIN, other conditions | combined | 76.8 [74.4, 79.5] | 78.1 [73.9, 82.6] | 75.6 [71.5, 79.6] | 78.9 [69.7, 86.9] | +0.8 [-9.3, 10.3] |
| Fitzpatrick17k in scope | not flagged by kNN | 82.6 [81.6, 83.7] | 83.7 [82.4, 85.0] | 83.7 [81.9, 85.7] | 79.9 [76.1, 83.4] | -3.8 [-7.7, 0.1] |
| Fitzpatrick17k in scope | confidence only | 83.1 [82.4, 83.7] | 83.4 [82.5, 84.3] | 81.8 [80.6, 83.0] | 86.0 [84.2, 87.7] | +2.6 [0.5, 4.6] |
| Fitzpatrick17k in scope | combined | 69.0 [67.9, 70.1] | 70.0 [68.6, 71.3] | 68.9 [67.0, 70.9] | 69.4 [65.7, 72.7] | -0.6 [-4.6, 3.0] |
| Fitzpatrick17k out of scope | not flagged by kNN | 81.1 [80.4, 81.7] | 82.1 [81.2, 83.0] | 83.8 [82.8, 84.8] | 79.0 [77.2, 80.7] | -3.1 [-5.2, -1.3] |
| Fitzpatrick17k out of scope | confidence only | 81.4 [81.1, 81.8] | 80.3 [79.7, 80.9] | 81.5 [80.9, 82.1] | 84.6 [83.6, 85.6] | +4.3 [3.1, 5.4] |
| Fitzpatrick17k out of scope | combined | 66.1 [65.5, 66.8] | 66.1 [65.2, 67.0] | 68.2 [67.1, 69.2] | 67.4 [65.7, 69.1] | +1.3 [-0.7, 3.2] |
| DDI out of scope | not flagged by kNN | 71.6 [67.9, 75.3] | 77.6 [70.6, 83.9] | 71.6 [65.5, 77.4] | 66.5 [59.9, 73.8] | -11.0 [-19.6, -1.0] |
| DDI out of scope | confidence only | 78.6 [76.4, 80.7] | 74.8 [69.9, 79.1] | 77.2 [73.2, 80.7] | 83.4 [79.9, 86.7] | +8.6 [3.1, 14.3] |
| DDI out of scope | combined | 56.0 [52.7, 59.4] | 57.7 [51.5, 63.7] | 54.6 [49.0, 59.9] | 56.2 [50.0, 63.1] | -1.5 [-10.0, 7.9] |
| DDI malignant | not flagged by kNN | 76.4 [71.1, 82.3] | 78.2 [68.5, 88.5] | 72.3 [64.3, 81.3] | 81.0 [70.0, 91.1] | +2.9 [-12.2, 16.9] |
| DDI malignant | confidence only | 79.5 [75.7, 82.9] | 79.0 [72.6, 85.1] | 74.9 [68.8, 80.7] | 87.3 [80.8, 92.7] | +8.3 [-0.4, 17.1] |
| DDI malignant | combined | 60.8 [55.6, 66.5] | 63.3 [53.7, 72.8] | 52.8 [44.3, 61.3] | 70.4 [58.2, 80.4] | +7.2 [-8.0, 20.4] |

## Answered with a label (%), by eMST group

Flagged by kNN: share NOT flagged. Confidence only: the E4 rule (calibrated confidence >= tau). Combined: confident and not flagged. On in-scope sets a higher share is better; on out-of-scope and malignant sets a lower share is safer.

| Set | Rule | ALL | 1-3 | 4-6 | 7-10 | 4-6 - 1-3 |
|---|---|---|---|---|---|---|
| SCIN test (in scope) | not flagged by kNN | 94.9 [94.0, 95.7] | 95.5 [94.5, 96.4] | 93.4 [91.6, 95.2] | 93.9 [89.0, 98.1] | -2.1 [-4.2, -0.1] |
| SCIN test (in scope) | confidence only | 79.8 [78.4, 81.3] | 80.4 [78.6, 82.2] | 77.2 [74.2, 80.1] | 86.8 [80.4, 92.7] | -3.2 [-6.5, 0.3] |
| SCIN test (in scope) | combined | 75.9 [74.3, 77.5] | 77.0 [75.1, 78.8] | 72.2 [69.1, 75.5] | 81.6 [74.0, 88.7] | -4.8 [-8.5, -0.9] |
| SCIN, other conditions | not flagged by kNN | 95.4 [93.5, 97.1] | 96.0 [93.7, 97.9] | 95.0 [91.2, 97.8] | 88.9 [72.7, 100.0] | -1.0 [-5.4, 2.8] |
| SCIN, other conditions | confidence only | 80.3 [77.9, 82.7] | 79.7 [76.7, 82.7] | 82.1 [77.6, 86.3] | 77.9 [65.8, 88.9] | +2.4 [-3.0, 7.7] |
| SCIN, other conditions | combined | 76.8 [74.4, 79.5] | 76.9 [73.5, 79.9] | 77.8 [72.5, 82.6] | 70.5 [53.0, 85.5] | +0.9 [-4.9, 7.3] |

## Selective accuracy on SCIN test (%), answered cases only

| Rule | ALL | eFST I-II | eFST III-IV | eFST V-VI |
|---|---|---|---|---|
| confidence | 67.7 [65.8, 69.7] | 68.5 [65.3, 71.4] | 66.6 [63.7, 69.4] | 67.2 [59.9, 74.3] |
| combined | 68.4 [66.3, 70.5] | 68.8 [65.6, 71.8] | 67.7 [64.7, 70.7] | 67.9 [60.5, 75.2] |
