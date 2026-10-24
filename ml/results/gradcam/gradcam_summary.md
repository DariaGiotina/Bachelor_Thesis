# Task 4.3: Grad-CAM sanity checks and map statistics

Seeds [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], SCIN test split, heatmap of the predicted class. Mean ± sd over cases.

## Model-randomization check (Spearman correlation with the trained model's map; near 0 = the map depends on the learned weights, as it should)

| Model | classifier randomised | classifier + top of encoder randomised | top-10% mass share | padding ratio |
|---|---|---|---|---|
| DINOv2 + linear probe | 0.02 ± 0.24 | 0.02 ± 0.21 | 0.39 ± 0.10 | 0.81 ± 0.56 |
| EfficientNet-B0 fine-tuned | 0.10 ± 0.44 | 0.02 ± 0.39 | 0.32 ± 0.11 | 0.33 ± 0.34 |

Padding ratio: heatmap mass per padding pixel relative to the image average (1 = no preference); computed on cases with letterbox padding only.

## Map statistics by outcome and eFST group (top-10% mass share)

| Model | outcome | I-II | III-IV | V-VI | cases (I-II / III-IV / V-VI) |
|---|---|---|---|---|---|
| DINOv2 + linear probe | correct | 0.409 | 0.391 | 0.385 | 621 / 647 / 122 |
| DINOv2 + linear probe | wrong | 0.381 | 0.385 | 0.395 | 287 / 324 / 59 |
| DINOv2 + linear probe | abstained | 0.372 | 0.362 | 0.369 | 263 / 230 / 45 |
| EfficientNet-B0 fine-tuned | correct | 0.306 | 0.303 | 0.308 | 576 / 556 / 105 |
| EfficientNet-B0 fine-tuned | wrong | 0.304 | 0.302 | 0.331 | 336 / 387 / 74 |
| EfficientNet-B0 fine-tuned | abstained | 0.359 | 0.365 | 0.372 | 259 / 258 / 47 |
