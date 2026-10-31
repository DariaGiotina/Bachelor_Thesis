# Task 4.7: fine-tuned DINOv2 and the border-artefact fixes

| model | macro_f1 | balanced_acc | ece_after | aurc | selective_accuracy |
|---|---|---|---|---|---|
| Photo, EfficientNet-B0 fine-tuned | 0.519 ± 0.040 | 0.610 ± 0.038 | 0.074 ± 0.020 | 0.345 ± 0.039 | 0.607 ± 0.028 |
| DINOv2 + probe | 0.551 ± 0.064 | 0.635 ± 0.059 | 0.061 ± 0.014 | 0.256 ± 0.043 | 0.676 ± 0.025 |
| DINOv2 + probe, mirrored padding | 0.537 ± 0.051 | 0.613 ± 0.072 | 0.069 ± 0.015 | 0.273 ± 0.028 | 0.656 ± 0.026 |
| DINOv2 with registers + probe | 0.528 ± 0.050 | 0.623 ± 0.079 | 0.080 ± 0.024 | 0.272 ± 0.040 | 0.662 ± 0.027 |
| DINOv2 fine-tuned | 0.589 ± 0.037 | 0.631 ± 0.041 | 0.061 ± 0.016 | 0.200 ± 0.031 | 0.706 ± 0.022 |
