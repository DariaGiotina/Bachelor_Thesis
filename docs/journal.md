# Thesis journal

Running log of decisions and why. Newest first.

## 2026-10-08: Skin-tone scales explained in thesis and paper

- **Done:** thesis section 5.3 and paper section 3.3 define FST, eFST and eMST and what each group (I-II, III-IV, V-VI; 1-3, 4-6, 7-10) means. Sources: Fitzpatrick 1988 (doi 10.1001/archderm.1988.01670060015008) and the Monk Skin Tone Scale (https://skintone.google/).
- **Why:** a reader of the tables cannot interpret the groups without the scale definitions. Rule going forward: every new term is explained where it first appears.

## 2026-10-08: Label derivation and class-set freeze (Task 1.2)

- **Done:** `ml/labels/label_map.yaml` (5 target categories, explicit string-to-category dictionary, `min_weight` 0.40) and `ml/labels/build_labels.py`. Outputs `scin_labels.csv` and `class_counts_by_tone.csv` in `ml/labels/` (the raw SCIN file of the same name lives in git-ignored `ml/data/scin/`).
- **Rule:** per `case_id`, weights of strings in the same category are summed; the largest sum is the primary label if >= `min_weight`. Ties, sub-threshold cases and unmapped strings become `excluded`.
- **Result (US eMST pool):** acne 144, eczema_dermatitis 1,068, redness_rosacea 44, normal_other 553, excluded 3,224 (1,972 have no weighted label). eFST V-VI: acne 10, redness_rosacea 1.
- **Assumptions:** folliculitis grouped with acne; seborrheic dermatitis and lichen simplex chronicus with eczema_dermatitis; unlisted strings (254 distinct, 884 mentions) go to `excluded`; eMST pool = US (CLI `--mst-pool`).
- **Open:** redness_rosacea is too small for per-tone results; consider merging it or reporting it descriptively only. Confirm eMST pool.

## 2026-10-07: SCIN download, licence check, metadata audit (Task 1.1)

- **Done:** downloaded the SCIN v1.0.0 metadata CSVs (`scin_cases`, `scin_labels`, plus the two question-description files) from `gs://dx-scin-public-data` into `ml/data/scin/` (git-ignored). Added `ml/scripts/audit_scin.py`, which writes `ml/reports/scin_schema.json`, `ml/reports/scin_audit_report.md` and the SCIN row of `ml/data_sources.csv`.
- **Licence:** SCIN Data Use License (https://github.com/google-research-datasets/scin/blob/main/LICENSE). Reproduction, sharing and adaptation are allowed with attribution. Any re-identification attempt is prohibited and immediately terminates the licence rights. Decision: research use only, never redistribute images.
- **Key numbers:**
  - 5,033 cases and 10,407 images (2.07 per case on average).
  - Every `case_id` is unique and present in both files.
  - Natural missingness: age unknown 56.9%, self-reported FST 56.8%, race 47.3%, symptoms 25.1%, duration 20.6%, texture and body part about 19%.
  - eFST V-VI: 436 cases (8.7%); FST VI alone: 68 cases. eMST 7-10: 4.1% with the US annotators vs 1.0% with the India annotators.
  - 60.8% of cases have a condition label. 38.3% of images were rated insufficient quality.
  - Acne is the top label for only 61 cases and rosacea for 29, against 488 for eczema.
- **Decisions:**
  - Multi-select questions (YES/blank columns) are assessed per question, not per column, because blank means "not ticked".
  - Sentinel answers such as AGE_UNKNOWN are counted separately from true NaNs.
  - eFST is the median of the available dermatologist labels, rounded half up.
  - Splits are made by `case_id`.
- **Open:**
  - Choose the eMST annotator pool (US or India).
  - The class set must account for the small acne and rosacea counts. Consider grouping, e.g. eczema/dermatitis, urticaria, infection-type, acne/folliculitis, other.
  - Images are not downloaded yet.
  - Verify the DDI and Fitzpatrick17k licences.
- **Docs:** paper section 3.1 added. Thesis section 5.1 is ready in `docs/tools/updates/2026-10-07_scin_audit.py` and is applied once the thesis .docx is closed in Word.
