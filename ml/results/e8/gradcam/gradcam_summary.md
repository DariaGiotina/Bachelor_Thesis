# Task 4.3: Grad-CAM sanity checks and map statistics

Seeds [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], SCIN test split, heatmap of the predicted class. Mean ± sd over cases.

## Model-randomization check (Spearman correlation with the trained model's map; near 0 = the map depends on the learned weights, as it should)

| Model | classifier randomised | classifier + top of encoder randomised | top-10% mass share | padding ratio | padding ratio, median | cases with padding ratio > 2 |
|---|---|---|---|---|---|---|
| DINOv2 + probe, mirrored padding | 0.03 ± 0.21 | -0.00 ± 0.16 | 0.44 ± 0.11 | 0.87 ± 0.33 | 0.86 | 0.4% |
| DINOv2 with registers + probe | -0.01 ± 0.28 | 0.13 ± 0.24 | 0.45 ± 0.15 | 0.77 ± 0.74 | 0.55 | 6.9% |
| DINOv2 fine-tuned | 0.01 ± 0.24 | 0.09 ± 0.19 | 0.37 ± 0.09 | 0.82 ± 0.54 | 0.70 | 3.0% |

Padding ratio: heatmap mass per padding pixel relative to the image average (1 = no preference); computed on cases with letterbox padding only.

## Map statistics by outcome and eFST group (top-10% mass share)

| Model | outcome | I-II | III-IV | V-VI | cases (I-II / III-IV / V-VI) |
|---|---|---|---|---|---|
| DINOv2 + probe, mirrored padding | correct | 0.466 | 0.467 | 0.446 | 594 / 641 / 131 |
| DINOv2 + probe, mirrored padding | wrong | 0.417 | 0.419 | 0.439 | 341 / 324 / 65 |
| DINOv2 + probe, mirrored padding | abstained | 0.412 | 0.419 | 0.417 | 236 / 236 / 30 |
| DINOv2 with registers + probe | correct | 0.491 | 0.465 | 0.453 | 607 / 631 / 128 |
| DINOv2 with registers + probe | wrong | 0.415 | 0.432 | 0.415 | 316 / 333 / 57 |
| DINOv2 with registers + probe | abstained | 0.446 | 0.426 | 0.400 | 248 / 237 / 41 |
| DINOv2 fine-tuned | correct | 0.377 | 0.368 | 0.359 | 655 / 680 / 133 |
| DINOv2 fine-tuned | wrong | 0.361 | 0.365 | 0.351 | 268 / 303 / 52 |
| DINOv2 fine-tuned | abstained | 0.370 | 0.351 | 0.340 | 248 / 218 / 41 |
