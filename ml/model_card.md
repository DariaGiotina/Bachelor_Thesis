# Model card: skin-concern classifier of the app

Format after Mitchell et al., "Model Cards for Model Reporting", FAT* 2019 (https://doi.org/10.1145/3287560.3287596).
Numbers: SCIN test split, mean ± sd over 10 split seeds unless stated otherwise; sources in
`results/results_registry.csv`. Export and its check: `export_model.py`, `results/export/export_check.md`.

## Model

- **What it is:** a frozen DINOv2 ViT-B/14 image encoder (86 M parameters, self-supervised on LVD-142M,
  `timm/vit_base_patch14_dinov2.lvd142m`) followed by one linear layer (the probe) trained on SCIN.
  Temperature scaling calibrates the probabilities; a confidence threshold tau and a kNN distance filter
  decide when the app shows no category.
- **Exported file:** `export/skin_concern_dinov2.onnx` (ONNX opset 18, 335 MB, not in the repository) with
  `export/skin_concern_dinov2.json` (classes, T, tau, kNN threshold, preprocessing, SHA-256). Probe of split
  seed 0, fixed by rule (the development seed), not chosen for its test score.
- **Input:** one RGB photo; longest side to 448 px, then to 518 px, centred black padding (`serving.preprocess`).
- **Output:** probabilities of 4 categories (acne, eczema_dermatitis, redness_rosacea, normal_other) and a
  decision: `answered` (category shown with its confidence), `uncertain` (confidence below tau = 0.488) or
  `unusual_photo` (kNN score above 0.455: the photo is unlike every training photo).
- **Licences:** DINOv2 weights Apache 2.0; SCIN Data Use License (no re-identification of the people in the
  photos). Fitzpatrick17k, DDI, PanDerm and DermLIP are not part of the model.
- **Version:** 2026-10-27, PyTorch 2.14.1, timm 1.0.30, ONNX Runtime 1.31.1 (`requirements-lock.txt`).

## Intended use

- Informational only: tells the user which of four common skin-concern categories a photo **may indicate**,
  with a confidence, and when to consult a professional. It is not a medical device, gives no diagnosis
  and no treatment advice.
- Users: adults using the app on their own photos. Runs on the server (FastAPI); too large for the phone.

## Out of scope

- Any condition outside the four categories, including skin cancer. The model was never trained on them and
  its confidence does not detect them (see Limitations).
- Children, mucous membranes, hair and nails, photos of other people.
- Any decision about care: the app always shows a permanent notice and asks red-flag questions (new or
  changing lesion, bleeding, pain) independently of the model.

## Training data

- SCIN (Google, release 1.0.0): consented contributors in the USA, smartphone photos, dermatologist
  differentials. 1,809 cases with a label (acne 144, eczema_dermatitis 1,068, redness_rosacea 44,
  normal_other 553); split by case into 70/15/15%; the shipped probe saw the 1,266 training cases of seed 0.
- Labels are weighted dermatologist differentials from photos and answers, not biopsy results.
- Skin tones are uneven: eFST V-VI 8.7% and eMST 7-10 4.1% of SCIN cases.

## Results (SCIN test, 10 seeds)

| Metric | Value |
|---|---|
| Macro-F1 (all cases) | 0.551 ± 0.064 |
| Balanced accuracy | 0.635 ± 0.059 |
| ECE after temperature scaling | 0.061 ± 0.014 |
| Coverage at tau (target 80%) | 79.8% |
| Selective accuracy (answered cases) | 67.7% |
| AURC (lower is better) | 0.256 ± 0.043 |

Comparison: the fine-tuned EfficientNet-B0 photo model reaches macro-F1 0.519 and selective accuracy 60.7%.
The macro-F1 advantage of DINOv2 (+0.032) is likely but not certain (t interval over seeds [-0.018, +0.082]);
the choice rests on calibration, selective accuracy and the licence.

## Results by skin tone

| Group | Macro-F1 | Coverage | Selective accuracy |
|---|---|---|---|
| eFST I-II | 0.537 | 77.5% | 68.5% |
| eFST III-IV | 0.560 | 80.8% | 66.6% |
| eFST V-VI (about 23 cases per seed) | 0.605 | 81.0% | 67.2% |
| eMST 1-3 | 0.564 | 80.4% | 68.9% |
| eMST 4-6 | 0.532 | 77.2% | 64.0% |
| eMST 7-10 (about 11 cases per seed) | 0.659 | 86.8% | 71.7% |

The model abstains about equally often in every group, but is less often right when it answers on eMST 4-6
than on 1-3 (-4.9 points, 95% interval [-9.3, -0.4]). eFST V-VI and eMST 7-10 are too small for conclusions.
On Fitzpatrick17k (atlas photos, not used for training) macro-F1 is 0.517 / 0.524 / 0.460 for eFST
I-II / III-IV / V-VI: darker skin stays the weakest group outside SCIN.

## Limitations and risks

- **Out-of-scope conditions:** without the kNN filter the model gives a confident benign category to 79.5%
  of the 171 biopsy-proven malignant lesions of DDI (87.3% on FST V-VI); with the filter 60.8% (70.4%).
  The filter recognises unusual photos, not unknown diseases (SCIN photos of other conditions are flagged
  only 4.6% of the time). The app therefore never presents the result as a safety check.
- **Fairness of the filter:** it flags 8.8% of normal SCIN photos of eFST V-VI vs 3.6% of I-II, so users with
  darker skin get "unusual photo" more often.
- **redness_rosacea** has 44 training cases; its results are unstable.
- **Questionnaire:** not used. It gave no measurable gain over the photo (E1, E2), so the app asks questions
  for safety and context only.
- One seed is shipped; its own test result (macro-F1 0.614) is above the 10-seed mean by chance of the split.
  The expected performance is the 10-seed mean.

## Equivalence of the exported file

ONNX Runtime vs PyTorch on the 270 test cases of seed 0: largest probability difference 6.7e-6, same class
for 100% of cases; same class as the stored E5 predictions for 99.6% (one case changes between mixed and full
precision). T, tau and the kNN threshold refitted on full-precision features agree with E4 (T 0.857 vs 0.857,
tau 0.488 vs 0.487).
