# E5: frozen encoders + linear probe

| model | macro_f1 | balanced_acc | ece |
|---|---|---|---|
| Photo, EfficientNet-B0 fine-tuned | 0.519 ± 0.040 | 0.610 ± 0.038 | 0.079 ± 0.017 |
| EfficientNet-B0 ImageNet + probe | 0.447 ± 0.029 | 0.543 ± 0.065 | 0.139 ± 0.090 |
| ViT-B/16 ImageNet-21k + probe | 0.450 ± 0.043 | 0.542 ± 0.069 | 0.095 ± 0.028 |
| DINOv2 + probe | 0.551 ± 0.064 | 0.635 ± 0.059 | 0.083 ± 0.027 |
| PanDerm-Base + probe | 0.553 ± 0.049 | 0.642 ± 0.071 | 0.128 ± 0.071 |
| PanDerm-Large + probe | 0.566 ± 0.044 | 0.662 ± 0.065 | 0.113 ± 0.062 |
| DermLIP + probe | 0.603 ± 0.046 | 0.689 ± 0.056 | 0.161 ± 0.115 |
