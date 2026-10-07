# Thesis journal

Running log of decisions and why. Newest first.

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
