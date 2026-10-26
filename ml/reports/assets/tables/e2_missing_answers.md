# RQ2: macro-F1 by share of hidden answers

| model | 0% hidden | 25% hidden | 50% hidden | 75% hidden | 100% hidden |
|---|---|---|---|---|---|
| Photo, EfficientNet-B0 fine-tuned | 0.519 | 0.519 | 0.519 | 0.519 | 0.519 |
| Concat, no dropout | 0.505 | 0.506 | 0.506 | 0.499 | 0.504 |
| Concat, fixed dropout | 0.514 | 0.508 | 0.511 | 0.508 | 0.505 |
| Concat, random dropout | 0.510 | 0.509 | 0.508 | 0.508 | 0.507 |
