# Exported app model: check (Task 4.5)

Model: DINOv2 ViT-B/14 (frozen) + linear probe, SCIN only; probe of split seed 0 (L2 0.1); ONNX opset 18; SHA-256 `6ed60809e644c604...`.

Calibration fitted on the fp32 validation features: T = 0.857 (E4 stored 0.857), tau = 0.488 (E4 0.487) for 80.0% coverage; kNN threshold 0.4548 (k = 10, 5.0% of validation cases flagged, bank of 1266 train cases).

## Equivalence

| Check | Value |
|---|---|
| Cosine similarity fp32 vs cached mixed-precision features (min / mean) | 0.99998 / 0.999998 |
| Largest difference ONNX vs PyTorch, probabilities | 6.71e-06 |
| Largest difference ONNX vs PyTorch, kNN score | 3.52e-06 |
| Same class ONNX vs PyTorch | 100.0% |
| Same class ONNX vs stored E5 predictions | 99.6% |
| ONNX Runtime on CPU, ms per image (with reading the photo) | 1172.8 |

## Test split of seed 0 (270 cases)

| | Accuracy | Macro-F1 | Coverage | Selective accuracy |
|---|---|---|---|---|
| Stored E4 result | 65.2% | 0.616 | 80.4% | 70.5% |
| Exported model, confidence rule | 64.8% | 0.614 | 80.0% | 70.4% |
| Exported model, kNN filter + confidence | 64.8% | 0.614 | 78.1% | 70.1% |

kNN filter flags 2.6% of the test cases.

One seed only: the expected performance of the model is the 10-seed mean in the result tables, not this row.
