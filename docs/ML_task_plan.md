# ML task plan (revised 2026-10-24, Weeks 2-3 closed the same day)

Status of every task of the original four-week program, and the changes made to the remaining tasks after the results of E1, E2 and E7. Status legend: DONE, PARTIAL, TODO, NEW (added after the original plan).

## Assumptions

- **Stack and hardware:** PyTorch 2.14 + timm 1.0.30, run locally on a Windows 11 PC with an NVIDIA RTX 3060 (CUDA 12.6). Colab / Kaggle are only a backup. (Original plan: Colab / Kaggle.)
- **Unit of splitting:** SCIN `case_id` is the contributor/case unit and the grouping key for splits.
- **Datasets:** SCIN is the training and main test set. DDI and Fitzpatrick17k are used for image-only evaluation, never for fusion (they have no questionnaire). Fitzpatrick17k images may also be used for research-only training (experiment E7), but never in the shipped model, the repository, the thesis or the paper; the images and every E7 checkpoint are deleted when the research ends (data-use agreement).
- **Class rule:** per case, the weights of all dermatologist differentials mapped to the same coarse class are summed; the largest sum is the label if it is at least `min_weight` = 0.40, otherwise the case is `excluded`. Result: 4 training classes (acne, eczema_dermatitis, redness_rosacea, normal_other) and 1,809 usable cases.
- **Seeds:** 10 split seeds (0-9), not 5, because the differences between models turned out to be smaller than the seed-to-seed spread.
- **Main finding that changes the plan:** the questionnaire adds no measurable gain over the photo (RQ1: paired macro-F1 difference of fusion vs photo within about +/-0.02 at 95%). Hiding answers therefore costs nothing (RQ2), and the model that will ship in the app is the photo-only model. Fusion stays a research result.
- Items marked [CITE] or [VERIFY] need a source before they go in the paper.
- Every task ends with one descriptive Git commit (rule: one commit per prompt).

## Week 1: Data foundation

**Task 1.1: SCIN Download, Licence Check & Audit - DONE (2026-10-07)**
- **Objective:** Download SCIN and record the exact schema, image counts, and cases with multiple images. Count missingness per field and the distribution of eFST/eMST. Record the licence terms.
- **Deliverable:** `audit_scin.py`, `scin_audit_report.md`, `scin_schema.json`, `data_sources.csv` (source, licence, counts). All exist.
- **Result:** 5,033 cases, 10,407 images; SCIN Data Use License verified (no re-identification, research use, no redistribution of images).

**Task 1.2: Label Derivation & Class Set Freeze - DONE (2026-10-08)**
- **Objective:** Parse the dermatologist differentials and weights, map conditions to coarse classes, apply the confidence-threshold rule, tabulate cases per class per skin-tone group, choose the final class set and the "excluded" policy.
- **Deliverable:** `build_labels.py`, `label_map.yaml`, `scin_labels.csv`, `class_counts_by_tone.csv`.
- **Result:** counts acne 144, eczema_dermatitis 1,068, redness_rosacea 44, normal_other 553, excluded 3,224. redness_rosacea has 1 case in eFST V-VI, so its per-tone result is descriptive only.

**Task 1.3: Questionnaire Schema, Missingness Mask & Encoder Spec - DONE (2026-10-08)**
- **Objective:** Select the questionnaire-style SCIN fields, document the SCIN-to-app mapping, build the feature vector plus a per-field missing mask, keep "unknown" distinct from "not answered".
- **Deliverable:** `questionnaire_schema.yaml`, `encode_questionnaire.py`, `field_mapping.md`, `questionnaire_features.parquet` (40 feature columns + 6 mask columns, no imputation).
- **Open:** the app questionnaire screen does not exist yet; `field_mapping.md` proposes its keys.

**Task 1.4: Case-Level Splits & Leakage Tests - DONE (2026-10-08, extended)**
- **Objective:** Grouped train/val/test splits by `case_id`, stratified on label x skin tone, with seed-specific variants and leakage tests.
- **Deliverable:** `make_splits.py`, `train_val_test_splits.json`, `test_no_leakage.py`, `split_summary.csv`.
- **Result:** 70/15/15 = 3,523 / 755 / 755 cases per seed, seeds 0-9. Leakage tests pass. A separate duplicate-safe split exists for Fitzpatrick17k (`make_fitzpatrick_splits.py`).

**Task 1.5: Dataset/DataLoader, Augmentation & Config Utilities - DONE (2026-10-08)**
- **Deliverable:** `data_loading.py`, `configs/base.yaml`, `utils/seed.py`, `sanity_batch.png` (git-ignored: it shows real SCIN photos).
- **Rule:** train picks one random image per case per epoch; val/test use `image_1_path`.

## Week 2: Image baseline & evaluation harness

**Task 2.1: Reusable Training/Eval Engine - DONE**
- `train.py`, `engine.py`, `losses.py` (weighted cross-entropy, focal), AMP, early stopping on validation macro-F1, `runs/<exp>/log.csv`.

**Task 2.2: Staged Fine-Tuning of the Image Baseline - DONE**
- `models/image_model.py` with `set_stage(1|2|3)`; EfficientNet-B0 and MobileNetV3 compared; winner chosen on validation macro-F1 only (EfficientNet-B0, weighted loss).

**Task 2.3: Evaluation Harness - DONE**
- `src/skinconcern/metrics.py` and `evaluate.py`: balanced accuracy, macro-F1, per-class and per-tone metrics, worst-group gap, case-level bootstrap CIs, ECE, reliability table, risk-coverage curve, AURC.

**Task 2.4: Multi-Seed Image-Only Baseline (E1 arm 1) - DONE (2026-10-09)**
- `run_image_only.py`, imbalance ablation (weighted loss vs sampler). Result over 10 seeds: test macro-F1 0.519 +/- 0.040.

**Task 2.5: External Image-Only Baselines (DDI & Fitzpatrick17k) - DONE**
- **Done:** `external_datasets.py`; Fitzpatrick17k zero-shot on all 4,012 mapped images: macro-F1 0.393 +/- 0.016 (eFST I-II 0.412, III-IV 0.371, V-VI 0.312).
- **Done (E5, 2026-10-24):** linear probe on six frozen encoders, 10 seeds, `results/e5/e5_table.md` (arms `probe_*` in `run_e1.py`). Macro-F1 vs fine-tuned EfficientNet-B0 (0.519):
  - EfficientNet-B0 ImageNet 0.447 (-0.072), ViT-B/16 ImageNet-21k 0.450 (-0.069), both 0/10 seeds better;
  - DINOv2 ViT-B/14 0.551 (+0.032 [+0.005, +0.061], 7/10, t p = 0.185);
  - PanDerm-Base 0.553 (+0.034, 8/10, p = 0.069); PanDerm-Large 0.566 (+0.047 [+0.017, +0.078], 7/10, p = 0.022);
  - **DermLIP ViT-B/16 0.603 (+0.084 [+0.052, +0.114], 10/10, p < 0.001)**, best encoder.
  - Licences: PanDerm and DermLIP CC BY-NC-ND 4.0 (research only, no modified versions may be distributed); DINOv2 Apache 2.0. Recorded in `data_sources.csv`.
- **PanDerm loading:** `panderm:<base|large>` backbone in `foundation_probe.py` (BEiT-style weights converted to timm names, strict load, checked against the authors' code).
- **DDI (2026-10-24):** 656 images in `ml/data/ddi/images/`, checked: all files of the metadata present, readable, no exact duplicates, tones 208 / 241 / 207 (FST I-II / III-IV / V-VI); the copy of the metadata inside `images/` has the same rows (only the first column header differs). Only 178 images map to our classes (172 normal_other), so DDI is used in E4 (abstention on out-of-scope and malignant lesions), not for macro-F1.

## Week 3: Questionnaire encoding, late fusion & modality dropout

**Task 3.1: Questionnaire-Only Baseline (E1 arm 2) - DONE**
- `models/q_model.py`, `run_q_only.py`. Result: macro-F1 0.381 (chance 0.25).

**Task 3.2: Late-Fusion Model with Missing Indicator - DONE**
- `models/fusion_model.py` (`LateFusionNet`): concat, gated, FiLM.

**Task 3.3: E1 Runner & Comparison Table - DONE (2026-10-09)**
- `run_e1.py`, `results/e1/e1_summary.csv`, `e1_table.md`, 10 seeds. Photo 0.519; concat 0.514; gated 0.490 (worse); FiLM 0.519. Questionnaire adds no measurable gain.
- **Extra work (method check, 2026-10-10):** diagnostics, positive control, cross-fitted stacking and ceiling analysis show the null result is not a method error.

**Task 3.4: Modality & Answer Dropout Training - DONE (2026-10-10)**
- `dropout_utils.py`, `--q_dropout none|fixed|random` in `train.py` / `run_fusion.py`, `run_e2_dropout.py`.

**Task 3.5: Missingness Robustness Evaluation (E2) - DONE (2026-10-24)**
- **Random removal (2026-10-10):** 0/25/50/75/100% of answers hidden at test time, with and without dropout training, 10 seeds. Hiding all answers costs 0.001-0.010 macro-F1; no CI excludes 0.
- **Field-wise removal (`eval_missingness.py`):** hiding any single question, or keeping only one, changes macro-F1 by at most 0.010 in every fusion arm (concat nodrop / fixed / randdrop, FiLM); nothing survives Holm correction. No single question carries the signal.
- **Naturally missing subgroup:** per seed 139 complete, 95 partial, 37 empty test questionnaires (age excluded from the count: "age unknown" is an explicit answer). On empty questionnaires concat without dropout is -0.041 [-0.097, +0.014] vs photo-only; the dropout-trained arms are level (+0.002 to +0.009). Hint only (CI includes 0).
- **Deliverables:** `eval_missingness.py`, `results/e2/e2_missingness_results.csv`, `e2_missingness_summary.csv`, `e2_missingness_table.md`, `e2_curve.png`; tests `tests/test_eval_missingness.py`. Thesis 8.9 (Figure 8.1) / paper 4.9 (Figure 1).

## Week 4: Fairness, calibration, explainability & freeze

Recommended order (changed): 4.2, 4.3, 4.2b, 4.1, 4.4, 4.5 (all done). 4.2 and 4.3 go first because the app needs the "uncertain, see a professional" output and the explanation screen for the photo-only model, and E4 is the only research question without results.

**Task 4.1: Skin-Tone Stratified Analysis (E3) - DONE (2026-10-26)**
- **Code:** `analyze_fairness.py` reads the stored test predictions (nothing retrained) of the E1 arms, the E5 probes (DINOv2, DermLIP, PanDerm-Large), the E7 pooled model and the E2 hidden-answer runs (r = 1 vs 0), plus the Fitzpatrick17k zero-shot predictions of the two app candidates. Per eFST / eMST group: macro-F1 and balanced accuracy, paired difference vs the photo model (Holm within each model), missingness drop, best-minus-worst gap (groups with >= 20 cases; mean +- sd, no bootstrap interval because the range of noisy groups is biased upwards), groups with < 30 test cases per seed flagged as descriptive. Tests `tests/test_fairness_and_stats.py`.
- **Results (`results/e3/e3_table.md`, `e3_by_tone.csv`, `e3_benefit_by_tone.png`):** photo model weakest on eMST 4-6 (0.457); DINOv2 probe 0.532 (+0.075 [+0.023, +0.119], not Holm-significant), DermLIP 0.577 (+0.120, Holm-significant). No fusion helps any group (gated hurts eFST III-IV). Hiding all answers costs at most 0.023 in groups with >= 30 cases (FiLM eMST 4-6, CI includes 0); only significant loss -0.015 (concat with dropout, eMST 1-3). eFST V-VI (~23 cases) and eMST 7-10 (~11) are descriptive only. Fitzpatrick17k: photo 0.412 / 0.371 / 0.312 (gap 0.100), DINOv2 0.517 / 0.524 / 0.460 (gap 0.068), DINOv2 better in every tone (+0.105 to +0.153, all Holm-significant); V-VI stays the worst group.
- **Thesis:** 8.8 with Table 8.11.

**Task 4.2: Calibration & Abstention (E4) - DONE (2026-10-24)**
- **Code:** `calibrate.py` (temperature scaling by golden-section search on the validation NLL; re-exports full class probabilities for the photo-only and FiLM checkpoints, 100% agreement with the stored predictions), `abstain.py` (tau for a target coverage on validation, selective metrics, per-group bootstrap; cluster bootstrap by image for external sets), `run_e4.py`; tests `tests/test_calibrate_abstain.py`.
- **Results (`results/e4/e4_table.md`, 10 seeds, 80% target coverage):**
  - Temperature scaling brings every model to ECE 0.061-0.079 (PanDerm-Large 0.113 -> 0.067, DermLIP 0.161 -> 0.077, EfficientNet-B0 T = 0.93, nearly unchanged).
  - AURC vs EfficientNet-B0 (0.345): DINOv2 -0.089, PanDerm-Large -0.119, DermLIP -0.116 (10/10 seeds each); FiLM -0.023 (8/10).
  - Selective accuracy at 80% coverage: EfficientNet-B0 0.607, FiLM 0.616, DINOv2 0.676, PanDerm-Large 0.699, DermLIP 0.720.
  - **RQ4:** on SCIN the abstention rate is about equal across eFST / eMST groups (20-25%; only FiLM abstains less on eFST V-VI, -6.0 points), but selective accuracy is lower on eMST 4-6 than on 1-3 for every model (-4.6 to -8.9 points, all CIs below 0): equally often uncertain, not equally often right. Probes narrow the gap, do not close it. On Fitzpatrick17k (zero-shot) EfficientNet-B0 abstains more on dark skin (27.5% eFST I-II vs 38.8% V-VI, +11.2 [8.0, 14.1]) and is less accurate when it answers (-5.0 [-9.5, -0.4]).
- **Thesis 8.11 / paper 4.11** (Tables 8.10-8.11 / 11-12, Figures 8.2-8.3 / 2-3).
- **External (all Fitzpatrick17k and DDI images, `--keep_all` loader, cached in `runs/external_eval/e4/`):** in scope DINOv2 is far better on Fitzpatrick17k (accuracy 53.8% vs 42.9%, no tone gap). **But confidence does not catch out-of-scope conditions:** DINOv2 abstains on only 18.6% (Fitzpatrick17k) / 21.4% (DDI) of them, less on dark skin; it answers confidently with a benign category for **79.5% of the 171 DDI malignant lesions (87.3% on FST V-VI)**; EfficientNet-B0 55.0% (70.0%). Thesis 8.11 Table 8.12 / paper Table 13.
- `e4_reliability.png` (reliability diagram) is saved but not in the documents.

**Task 4.2b: Out-of-scope detector - DONE (2026-10-26)**
- **Why:** E4 shows that confidence-based abstention misses most out-of-scope and malignant lesions, and more so on dark skin.
- **Code:** `ood_detect.py` (scores on frozen DINOv2 features fitted per seed on SCIN train: max calibrated probability, Mahalanobis with Ledoit-Wolf covariance, kNN cosine distance with k = 10 = primary, fixed in advance; threshold = 95th percentile on validation), `labels/scin_near_ood.csv` (464 SCIN cases with every differential outside the categories; 463 images available), `download_scin_images.py --case-ids`, cached external features in `run_e4.external_features`; tests `tests/test_ood_detect.py`.
- **Results (`results/e4/e4_ood.md`, 10 seeds):** SCIN other conditions are not separated by any score (AUROC 0.50-0.53, kNN flags 4.6% vs 5.1% false alarms). External sets: Mahalanobis AUROC 0.77-0.89, kNN 0.72-0.83, confidence 0.46-0.51, but Fitzpatrick17k in-scope images are flagged as often as out-of-scope ones (17.4% vs 18.9%): the detector recognises the photo domain, not the condition. Combined rule (not flagged AND confidence >= tau): DDI malignant answered confidently 79.5% -> 60.8% (FST V-VI 87.3% -> 70.4%); SCIN coverage 79.8% -> 75.9%, selective accuracy unchanged. kNN false alarms higher on eFST V-VI (8.8% vs 3.6%).
- **Decision:** kNN stays as a filter for unusual photos; safety comes from red-flag questions, a permanent notice and the declared scope (requirements for Task 5.1). Mahalanobis needs a fresh set before it can replace kNN.
- **Thesis:** 8.6 (Table 8.9), 8.8.



**Task 4.3: Grad-CAM Explainability - DONE (2026-10-24)**
- **Code:** `run_gradcam.py` (DINOv2 + probe: last block input, patch tokens reshaped to 37 x 37; EfficientNet-B0: conv_head), all test cases of 10 seeds (2,708 per model), batch 4 (the ViT at 518 px otherwise overflows the 12 GB GPU).
- **Sanity check (Adebayo et al. 2018):** Spearman correlation with the trained map after randomizing the classifier: DINOv2 0.02 ± 0.24 (77.5% of cases |rho| < 0.3), EfficientNet-B0 0.10 ± 0.44 (41.7%); classifier + top of encoder: 0.02 for both. Both pass on average, DINOv2 more consistently.
- **Shortcut check:** DINOv2 puts more heat on the black letterbox padding (median ratio 0.67 vs 0.25; 3.7% of cases above 2x vs 0.6%), mostly for acne / normal_other predictions; known register-token artefact (Darcet et al. 2024). Map focus equal across tones.
- **Outputs:** `results/gradcam/gradcam_cases.csv`, `gradcam_summary.md`; overlay grids in `runs/gradcam/` (git-ignored, SCIN photos). Thesis 8.12 / paper 4.12.
- **Possible follow-up:** reflection padding instead of black borders, or DINOv2 with registers (`vit_base_patch14_reg4_dinov2`).

**Task 4.4: Statistical Tests & Result Tables/Figures - DONE (2026-10-26)**
- **Code:** `stats_tests.py` recomputes all 31 main contrasts (RQ1 E1, RQ2 E2, E5 encoders, E7 extra data, RQ4 AURC, Task 4.2b detectors) from the stored per-seed results with one procedure: per-seed difference, 95% t interval over seeds, paired t and Wilcoxon, Holm within each family and over all contrasts; the runners' stored contrasts (20) must agree (mean within 1e-4, p within 0.005) or the script stops. `make_report_assets.py` rebuilds 8 tables (CSV + Markdown, `--decimal-comma` for the Romanian thesis) and collects 6 figures with an index in `reports/assets/`.
- **Results (`results/stats/contrasts.md`):** all 20 stored contrasts reproduced. 12 of 31 stay significant after Holm over all: questionnaire-only and ImageNet-probe losses, DermLIP +0.084, AURC reduction of the three probes, detector differences. PanDerm-Large +0.047 (Holm all 0.381) and E7 pooled -0.035 (0.289) no longer pass; DINOv2 +0.032 has t interval over seeds [-0.018, +0.082] (case bootstrap [+0.005, +0.061]), so its macro-F1 advantage is likely but not certain; the app choice rests on calibration, selective accuracy and licence.
- **Thesis:** 8.8 (statistics paragraph).

**Task 4.5: Reproducibility Freeze & Model Export - DONE (2026-10-27)**
- **Export:** `export_model.py` puts the DINOv2 ViT-B/14 encoder, the linear probe of split seed 0 (fixed by rule), the temperature and the kNN out-of-scope score in one ONNX file (`export/skin_concern_dinov2.onnx`, opset 18, 335 MB, git-ignored) with a JSON of classes, T = 0.857, tau = 0.488, kNN threshold 0.455, preprocessing and SHA-256. Thresholds are refitted on fp32 validation features (the service runs in fp32) and agree with E4.
- **Checks (`results/export/export_check.md`):** ONNX vs PyTorch max probability difference 6.7e-6, same class 100%; same class as stored E5 predictions 99.6% (269/270); seed-0 test selective accuracy 70.4% vs 70.5% in E4.
- **Serving:** `serving.py` (preprocessing without PyTorch, tested equal to the evaluation transform; decision unusual photo -> uncertain -> answered).
- **Reproducibility:** `requirements-lock.txt`, `run_all.sh` (stages data / e1 / e2 / e5 / e7 / e4 / report / export / test), `results_registry.py` -> `results/results_registry.csv` (337 numbers; rebuilds all 8 thesis tables and stops on a difference). `run_e1.py --name` added because the E5 files had been renamed by hand; the rebuild reproduces them exactly.
- **Model card:** `model_card.md`.
- **Thesis:** section 6.1, Table 6.1.

## Added tasks (NEW)

**Task 4.0: Literature search and novelty check - NEW, start now, runs in parallel**
- **Objective:** read in full the three closest papers (S3 modified C-Tran on SCIN, S4 multimodal models with and without patient metadata, S5 dermatology-AI generalization gap by skin tone). Run the systematic search with the terms in the research-question draft (Google Scholar, Semantic Scholar, arXiv). Write the gap statement and the hypotheses H1-H4 for RQ1-RQ4. Agree the journal and scope with the coordinator.
- **Why now:** the paper deadline is December 2026 and novelty is the largest open risk. A null result for the questionnaire is publishable only if framed as a rigorous negative result with the fairness and missing-answer analysis.
- **Deliverable:** related-work table (paper, data, what it does, difference), hypotheses in the paper's research-question section.

**Task 4.6: DermLIP and DDI - DermLIP DONE, DDI waiting for the images (see 2.5)**
- **Possible follow-up:** fine-tune DINOv2 (the shippable encoder) instead of only probing it.

**Task 5.1: App backend and mobile MVP - NEW (outside the ML program, thesis milestone O3, 31.03.2027)**
- **Objective:** FastAPI skeleton (auth, `/analyze` serving the exported ONNX model with temperature and tau, MongoDB models from the EER design), then the Expo screens from the Figma designs.
- **Status (2026-10-28):** ML inference service done: `api/ml_service/app.py` (`GET /health`, `POST /v1/analyze` with the exported ONNX model, size / format / pixel limits, optional service key, raw-body upload read in memory with a cap, 9 tests). Still to do: main backend (auth, MongoDB), `api/main.py` empty, `app/SkincareApp` is the Expo template only.
