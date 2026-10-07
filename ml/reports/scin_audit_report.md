# SCIN metadata audit

Generated 2026-10-07 by `ml/scripts/audit_scin.py`. Licence: [SCIN Data Use License](https://github.com/google-research-datasets/scin/blob/main/LICENSE) (attribution required when sharing; re-identification of data subjects prohibited). Informational research use only.

## 1. Overview

| metric | value |
|---|---|
| Cases (unique `case_id`) | 5033 |
| Images (non-empty image paths) | 10407 |
| Mean images per case | 2.068 |
| Columns in cases CSV | 57 |
| Columns in labels CSV | 17 |

## 2. Key integrity (`case_id`)

| check | value |
|---|---|
| cases_rows | 5033 |
| labels_rows | 5033 |
| cases_null_ids | 0 |
| labels_null_ids | 0 |
| cases_duplicate_ids | 0 |
| labels_duplicate_ids | 0 |
| only_in_cases | 0 |
| only_in_labels | 0 |
| in_both | 5033 |

## 3. Images per case

| value | cases | pct |
|---|---|---|
| 1 | 1948 | 38.7 |
| 2 | 796 | 15.82 |
| 3 | 2289 | 45.48 |

## 4. Missing values

Multi-select questions are stored as one `YES`/blank column per option, so a blank cell there means *not ticked*. Their missingness is reported per question family (4.1). Single-value fields are reported per column (4.2); *sentinel* counts answers such as AGE_UNKNOWN, NONE_IDENTIFIED, OTHER_OR_UNSPECIFIED, PREFER_NOT_TO_ANSWER, UNKNOWN, which are present but uninformative.

### 4.1 Multi-select question families

| family | options | answered_cases | unanswered_pct | mean_options_ticked |
|---|---|---|---|---|
| race_ethnicity | 10 | 2652 | 47.31 | 1.05 |
| textures | 4 | 4079 | 18.95 | 1.32 |
| body_parts | 12 | 4085 | 18.84 | 1.96 |
| condition_symptoms | 8 | 3770 | 25.09 | 2.09 |
| other_symptoms | 7 | 3508 | 30.3 | 1.14 |

### 4.2 Single-value fields (top 25 by missing + sentinel)

| field | missing | missing_pct | sentinel | missing_or_sentinel_pct |
|---|---|---|---|---|
| dermatologist_fitzpatrick_skin_type_label_3 | 4402 | 87.46 | 0 | 87.46 |
| dermatologist_fitzpatrick_skin_type_label_2 | 4399 | 87.4 | 0 | 87.4 |
| dermatologist_gradable_for_skin_condition_2 | 4317 | 85.77 | 0 | 85.77 |
| dermatologist_gradable_for_skin_condition_3 | 4317 | 85.77 | 0 | 85.77 |
| dermatologist_gradable_for_fitzpatrick_skin_type_2 | 4317 | 85.77 | 0 | 85.77 |
| dermatologist_gradable_for_fitzpatrick_skin_type_3 | 4317 | 85.77 | 0 | 85.77 |
| age_group | 1 | 0.02 | 2864 | 56.92 |
| fitzpatrick_skin_type | 2530 | 50.27 | 328 | 56.79 |
| image_3_path | 2744 | 54.52 | 0 | 54.52 |
| image_3_shot_type | 2743 | 54.5 | 0 | 54.5 |
| sex_at_birth | 1 | 0.02 | 2559 | 50.86 |
| combined_race | 2381 | 47.31 | 34 | 47.98 |
| image_2_path | 1948 | 38.7 | 0 | 38.7 |
| image_2_shot_type | 1948 | 38.7 | 0 | 38.7 |
| related_category | 1254 | 24.92 | 0 | 24.92 |
| condition_duration | 997 | 19.81 | 39 | 20.58 |
| dermatologist_fitzpatrick_skin_type_label_1 | 731 | 14.52 | 0 | 14.52 |
| monk_skin_tone_label_us | 28 | 0.56 | 0 | 0.56 |
| monk_skin_tone_label_india | 14 | 0.28 | 0 | 0.28 |
| gradable_for_monk_skin_tone_india | 10 | 0.2 | 0 | 0.2 |
| gradable_for_monk_skin_tone_us | 10 | 0.2 | 0 | 0.2 |
| year | 0 | 0.0 | 0 | 0.0 |
| release | 0 | 0.0 | 0 | 0.0 |
| image_1_shot_type | 0 | 0.0 | 0 | 0.0 |
| image_1_path | 0 | 0.0 | 0 | 0.0 |

Full per-column figures are in `scin_schema.json`.

## 5. Skin tone

eFST = median of up to three dermatologist Fitzpatrick labels per case (rounded half up). eMST = Monk Skin Tone label from the US and India annotator pools.

### 5.1 eFST (dermatologist-estimated Fitzpatrick)

| value | cases | pct |
|---|---|---|
| 1 | 334 | 6.64 |
| 2 | 1439 | 28.59 |
| 3 | 1424 | 28.29 |
| 4 | 737 | 14.64 |
| 5 | 368 | 7.31 |
| 6 | 68 | 1.35 |
| missing | 663 | 13.17 |

| value | cases | pct |
|---|---|---|
| I-II | 1773 | 35.23 |
| III-IV | 2161 | 42.94 |
| V-VI | 436 | 8.66 |
| missing | 663 | 13.17 |

Number of dermatologist FST labels per case:

| value | cases | pct |
|---|---|---|
| 0 | 663 | 13.17 |
| 1 | 3707 | 73.65 |
| 2 | 129 | 2.56 |
| 3 | 534 | 10.61 |

### 5.2 Self-reported Fitzpatrick

| value | cases | pct |
|---|---|---|
| FST1 | 188 | 3.74 |
| FST2 | 542 | 10.77 |
| FST3 | 661 | 13.13 |
| FST4 | 427 | 8.48 |
| FST5 | 214 | 4.25 |
| FST6 | 143 | 2.84 |
| NONE_IDENTIFIED | 328 | 6.52 |
| missing | 2530 | 50.27 |

### 5.3 eMST (US annotators)

| value | cases | pct |
|---|---|---|
| 1 | 577 | 11.46 |
| 2 | 1660 | 32.98 |
| 3 | 1265 | 25.13 |
| 4 | 687 | 13.65 |
| 5 | 361 | 7.17 |
| 6 | 248 | 4.93 |
| 7 | 137 | 2.72 |
| 8 | 57 | 1.13 |
| 9 | 11 | 0.22 |
| 10 | 2 | 0.04 |
| missing | 28 | 0.56 |

| value | cases | pct |
|---|---|---|
| 1-3 | 3502 | 69.58 |
| 4-6 | 1296 | 25.75 |
| 7-10 | 207 | 4.11 |
| missing | 28 | 0.56 |

### 5.4 eMST (India annotators)

| value | cases | pct |
|---|---|---|
| 1 | 187 | 3.72 |
| 2 | 2427 | 48.22 |
| 3 | 1591 | 31.61 |
| 4 | 522 | 10.37 |
| 5 | 177 | 3.52 |
| 6 | 63 | 1.25 |
| 7 | 35 | 0.7 |
| 8 | 14 | 0.28 |
| 9 | 3 | 0.06 |
| missing | 14 | 0.28 |

| value | cases | pct |
|---|---|---|
| 1-3 | 4205 | 83.55 |
| 4-6 | 762 | 15.14 |
| 7-10 | 52 | 1.03 |
| missing | 14 | 0.28 |

### 5.5 eFST group x eMST (US) group

| eFST \ eMST | 1-3 | 4-6 | 7-10 | missing |
|---|---|---|---|---|
| I-II | 1611 | 156 | 1 | 5 |
| III-IV | 1387 | 738 | 30 | 6 |
| V-VI | 38 | 236 | 162 | 0 |
| missing | 466 | 166 | 14 | 17 |

## 6. Dermatologist condition labels

Cases with at least one weighted condition label: 3061 (60.8%). The table lists the 25 most frequent top-weighted conditions; these are dermatologist differentials, not confirmed outcomes.

| value | cases | pct |
|---|---|---|
| Eczema | 488 | 15.94 |
| Allergic Contact Dermatitis | 270 | 8.82 |
| Urticaria | 214 | 6.99 |
| Insect Bite | 185 | 6.04 |
| Folliculitis | 142 | 4.64 |
| Psoriasis | 109 | 3.56 |
| Tinea | 93 | 3.04 |
| Impetigo | 69 | 2.25 |
| Herpes Zoster | 68 | 2.22 |
| Pigmented purpuric eruption | 62 | 2.03 |
| Acne | 61 | 1.99 |
| Drug Rash | 58 | 1.89 |
| Herpes Simplex | 55 | 1.8 |
| Acute dermatitis, NOS | 46 | 1.5 |
| Pityriasis rosea | 44 | 1.44 |
| Irritant Contact Dermatitis | 39 | 1.27 |
| Tinea Versicolor | 37 | 1.21 |
| CD - Contact dermatitis | 36 | 1.18 |
| Keratosis pilaris | 32 | 1.05 |
| Lichen Simplex Chronicus | 32 | 1.05 |
| Rosacea | 29 | 0.95 |
| Viral Exanthem | 29 | 0.95 |
| Lichen planus/lichenoid eruption | 28 | 0.91 |
| O/E - ecchymoses present | 28 | 0.91 |
| Granuloma annulare | 27 | 0.88 |

Image-quality gradability (first dermatologist):

| value | cases | pct |
|---|---|---|
| DEFAULT_YES_IMAGE_QUALITY_SUFFICIENT | 3049 | 60.58 |
| NO_IMAGE_QUALITY_INSUFFICIENT | 1925 | 38.25 |
| YES_IMAGE_QUALITY_SUFFICIENT_NO_DISCERNIBLE_PATHOLOGY | 59 | 1.17 |

## 7. Notes for downstream use

- Split train/validation/test by `case_id`, never by image, so photos of one case stay together.
- Skin-tone groups V-VI (eFST) and 7-10 (eMST) are small; report confidence intervals for them.
- eMST labels from the US and India annotator pools differ; choose one pool and report it.
- Condition labels are retrospective dermatologist differentials from images and self-reported data.
