# Thesis journal

Running log of decisions and why. Newest first.

## 2026-10-08: Reusable training/evaluation engine (Task 2.1)

- **Done:** `ml/engine.py` (`train_one_epoch`, `evaluate`, `EarlyStopping`; AMP via `torch.autocast` + `GradScaler`; model-agnostic through an `adapt(batch, training)` function that maps a batch to the model's keyword arguments), `ml/losses.py` (class-weighted cross-entropy and focal loss) and a refactored `ml/train.py` (`--model dummy|image_only|fusion`, early stopping on validation macro-F1, `runs/<exp_name>/best_model.pt` and `log.csv` with train_loss, val_loss, val_macro_f1, epoch_time). Tests in `ml/tests/test_engine.py`.
- **Decisions:** early stopping and checkpointing use validation macro-F1 (patience 5), not accuracy, because the classes are imbalanced. Loss is chosen in `configs/base.yaml` (`loss_type`) or with `--loss-type`. The default model is a tiny `dummy` CNN so the pipeline can be tested fast; EfficientNet image-only (Task 2.2) and fusion are already selectable.
- **Checked:** smoke runs of `dummy` and `fusion` (focal loss, 2 epochs, 4-5 batches) ran end to end on the GPU and wrote the log and results files. These numbers are meaningless and not recorded. No real results exist yet.
- **Downloads:** all 3,886 images of the 1,809 training cases are now on disk (`ml/data/scin/images/`, git-ignored).
- **Docs:** engine, loss options, AMP and early stopping added to thesis 5.8 and paper 3.8; reference added: Focal Loss (Lin et al. 2017).
- **Open:** first real runs on seed 0 (image-only vs fusion), then the five seeds.

## 2026-10-08: Training script with modality dropout (Task 1.6, no results yet)

- **Done:** `ml/train.py` trains the late-fusion model (EfficientNet-B0 from timm + questionnaire branch) for one split seed, keeps the best-validation checkpoint and evaluates once on test, overall and per eFST group, with 0/25/50/75/100% of questionnaire fields hidden. `--image-only` trains the photo-only baseline. Defaults live in the `train:` block of `ml/configs/base.yaml`. Tests in `ml/tests/test_train_utils.py`.
- **Decisions:** the model input is `[q_vec, q_mask]` (46 numbers). Modality dropout hides the whole questionnaire with p = 0.3 and each field with p = 0.15; a hidden field gets features 0 and mask 1, like a real missing answer (no imputation). Class-weighted cross-entropy because of the imbalance (44 redness_rosacea vs 1,068 eczema_dermatitis). AdamW, lr 3e-4, cosine decay, 15 epochs, mixed precision.
- **Checked:** a 2-epoch, 5-batch smoke run on the images downloaded so far ran end to end (numbers meaningless, not recorded). No real results exist yet.
- **Docs:** thesis 5.8 and 5.10, paper 3.8 and 3.9 filled with the method; references added: EfficientNet, timm, AdamW, SGDR (all with URLs).
- **Open:** wait for the image download (about 2,000 of 3,886 done), then a short real run on seed 0, then 5 seeds for both models. Run outputs go to the git-ignored `ml/runs/`.

## 2026-10-08: Data loading, augmentation and config utilities (Task 1.5)

- **Done:** `ml/configs/base.yaml`, `ml/utils/seed.py` (`seed_everything`), `ml/data_loading.py` (`SCINDataset`, `get_dataloaders`, sanity grid), `ml/scripts/download_scin_images.py`, tests in `ml/tests/test_data_loading.py`.
- **Rules:** train picks one random image per case per epoch (draw derived from seed, epoch, index, so independent of workers); val/test always use `image_1_path`. Augmentation (flip, shift/scale/rotate, colour jitter) only on train; every split gets resize 224 + ImageNet normalisation. Missing/corrupt image: try the case's other images, else black image with `image_ok = 0`.
- **Decisions:** the `excluded` group is dropped, so 4 training classes and 1,809 cases (seed 0: 1,266 / 272 / 271). Hue jitter kept at 0.02 so skin colour is not distorted. `ShiftScaleRotate` replaced by `Affine` (deprecated in albumentations 2.x). Only 298 primary images were downloaded (about 300 MB) for the sanity check; full set is about 10 GB (`--all-images`).
- **Repo:** `sanity_batch.png` shows real SCIN photos, so it is git-ignored (decision: never redistribute images).
- **Docs:** the thesis and paper were renamed and restructured (`Teza_Licenta.docx`, `Paper_Skin_Concern.docx`). New section 5.7 (thesis) and 3.7 (paper); later sections renumbered. `DocEditor` added to `docs/tools/docx_tools.py` for the new structure.
- **Open:** refresh the table of contents in Word to fix page numbers. Download all images before training.
- **Update (same day):** `download_scin_images.py` got `--used-only` (only cases kept by `drop_labels`) plus timeouts and retries. Running `--used-only --all-images` fetches the 3,886 images of the 1,809 training cases (about 3.9 GB) into the git-ignored `ml/data/scin/images/`.

## 2026-10-08: Case-level splits and leakage tests (Task 1.4)

- **Done:** `ml/splits/make_splits.py`, `train_val_test_splits.json` (seeds 0-4, case_id lists), `split_summary.csv` and `ml/tests/test_no_leakage.py` (17 tests pass).
- **Method:** one row per `case_id`, so a case cannot span splits. Two-step stratified split on primary_label x eFST group (I-II, III-IV, V-VI, missing): 70/30, then 50/50. Strata under 4 cases are merged per label, then into `rare` (5 cases).
- **Result:** 3,523 / 755 / 755 cases per seed. eFST V-VI: 305 / 66 / 65.
- **Decisions:** all cases are split, including `excluded` (filter later when training); stratifying on eFST groups, not the six raw types, because raw types x labels are too sparse.
- **Limitation:** redness_rosacea has 44 cases and 1 in V-VI, so per-tone results are not usable for it.
- **Process:** from now on one commit per prompt.

## 2026-10-08: Questionnaire schema, missingness mask and encoder (Task 1.3)

- **Done:** `ml/features/questionnaire_schema.yaml`, `field_mapping.md`, `encode_questionnaire.py` and `questionnaire_features.parquet` (5,033 rows indexed by `case_id`, 40 feature columns + 6 mask columns, no NaN). Test in `ml/tests/test_encode_questionnaire.py`.
- **Decisions:** no imputation (missing field = 0 plus mask 1); explicit unknown answers keep their own indicator (mask 0); a multi-select question is missing only if no box is ticked; body area is multi-hot (the question is select-all), age and skin type are one-hot, duration is ordinal 1-8.
- **Found by validation:** duration has two values not in the first draft, `SINCE_CHILDHOOD` (ranked 8, longest) and `UNKNOWN` (own indicator).
- **Excluded:** sex, race/ethnicity (fairness only), systemic symptoms, `related_category` (contains ACNE, would leak the label).
- **Missing rates:** body area 18.8%, symptoms 25.1%, texture 19.0%, duration 19.8%, skin type 50.3%.
- **Repo:** the parquet is committed through a `.gitignore` exception; other parquet files stay ignored.
- **Open:** the app has no questionnaire screen yet; `field_mapping.md` proposes its keys.

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
