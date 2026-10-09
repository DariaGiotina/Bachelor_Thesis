# Thesis journal

Running log of decisions and why. Newest first.

## 2026-10-09: E1 runner, all fusion variants and the ensemble diagnostic (Task 3.3)

- **Done:** `ml/run_e1.py` trains any missing arm through the existing runners (seeds with results are reused), checks that all arms were tested on the same cases per seed, and writes `ml/results/e1/e1_summary.csv` and `e1_table.md` (committed; aggregate numbers only): per arm mean ± sd over seeds with a 95% seed-stratified case-bootstrap CI (2,000 resamples, the same resamples for all arms), and per pair the per-seed macro-F1 differences with paired case-bootstrap CIs, mean difference with CI, seeds won, paired t-test and Wilcoxon. New `ml/ensemble_image_q.py` (diagnostic arm: log-linear pooling of the photo-only and questionnaire-only probabilities, weight chosen on validation; no retraining). `run_q_only.py --skip-existing`. 7 new tests (101 pass).
- **Bug found and fixed:** the bootstrap CI of ECE could exclude the ECE itself (photo only: 0.070, CI [0.076, 0.114] after averaging seeds). ECE of resampled sets is biased upward (fewer distinct cases per bin, absolute gaps). `skinconcern.metrics.bias_corrected_ci` shifts the percentile interval by the bootstrap bias; used for ECE in `evaluate.py` (through `bootstrap_standard_metrics`) and `run_e1.py`. All per-seed metrics of earlier runs were re-scored from their saved predictions. Reference: Roelofs et al. 2022.
- **Runs (EfficientNet-B0, weighted loss, 5 seeds, about 15 min per arm):** gated 0.514 ± 0.040, FiLM 0.544 ± 0.043, concat without modality dropout 0.503 ± 0.046, ensemble 0.521 ± 0.035 (photo 0.537 ± 0.038, concat 0.516 ± 0.057, questionnaire 0.390 ± 0.038).
- **Paired vs photo only (mean [95% CI], seeds won):** FiLM +0.008 [-0.023, +0.038] 3/5; concat -0.021 [-0.051, +0.007] 2/5; gated -0.023 [-0.060, +0.011] 2/5; ensemble -0.016 [-0.053, +0.018] 1/5; concat no-dropout -0.033 [-0.067, -0.002] 0/5 (only significant difference, and it is negative).
- **All answers hidden:** concat 0.506, gated 0.521 (higher than with answers), FiLM 0.518 (only variant that loses something), no-dropout 0.495, ensemble 0.549 (higher than with answers: the questionnaire model's no-information output acts as a class-prior shift; not investigated further).
- **Conclusions (RQ1, this configuration):** no way of combining the inputs beats the photo; removing modality dropout made things worse, so dropout was not the reason the questionnaire was ignored; the ensemble's validation gain (w_image 0.4-0.7 in 3 seeds) did not carry over to test, so the questionnaire's signal looks redundant with the photo for these 4 categories rather than unused. Possible reason: body area and texture are visible in the photo. Five seeds detect differences of about 0.04 only.
- **Next (suggested):** per-class view of where the questionnaire could help (acne, the weakest class); E2 missing-answer curves are already in the files; image-only ablation (sampler, MobileNetV3) for the final backbone choice.
- **Docs:** thesis 5.10 / paper 3.9 (bias-corrected ECE interval); new thesis 8.3 / paper 4.3 with Table 8.3 / Table 3 (all arms, paired differences; log-linear pooling defined; references: Roelofs et al. 2022, Genest and Zidek 1986).

## 2026-10-09: Late-fusion model and first E1 comparison (Task 3.2)

- **Done:** `ml/models/fusion_model.py` (`LateFusionNet`): `SkinImageBaseline` in feature mode (new `num_classes=0`) + questionnaire encoder (2 x 64 over [q_vec, q_mask]) + fusion `concat` (default), `gated` (gated multimodal unit, gate inspectable with `gate_values`) or `film` (FiLM, starts as image-only). Same `set_stage` and parameter groups as the image baseline; the new layers train in every stage at the head rate. `train.py --model fusion [--fusion ...]` now builds it (old `FusionClassifier` no longer used by training; kept for the Grad-CAM wrapper and its tests). The staged loop moved into `run_image_only.fit_staged`, shared by `run_image_only.py` and the new `ml/run_fusion.py` (5 seeds, `--fusion`, `--balance`, `--no-dropout` for E2, checkpoints `seed_checkpoints/fusion_late_<variant>_seed{k}.pt`, summary `e1_fusion_test.csv`). Config block `fusion`. 13 new tests (94 pass).
- **Bug found and fixed:** MobileNetV3 returns 1,280 pooled features although timm's `num_features` is 960 (its conv_head comes after pooling), so a fusion head sized from `num_features` crashed. `SkinImageBaseline.num_features` now uses `head_hidden_size`; test added.
- **Real runs (EfficientNet-B0, weighted loss, seeds 0-4, about 3 min per seed):**
  - photo only: macro-F1 0.537 ± 0.038, bal-acc 0.624 ± 0.044, ECE 0.070, AURC 0.332; per class F1 eczema 0.691, redness 0.682, normal_other 0.437, acne 0.337; eFST I-II 0.538, III-IV 0.542, V-VI 0.490 ± 0.175 (worst group V-VI x3).
  - fusion concat: macro-F1 0.516 ± 0.057, bal-acc 0.595 ± 0.038, ECE 0.088 ± 0.056 (seed 4: 0.181), AURC 0.354; hidden answers 0/25/50/75/100% -> 0.516/0.510/0.518/0.511/0.506; eFST V-VI 0.445 ± 0.085.
  - paired difference fusion - photo: -0.021 ± 0.031 (per seed -0.053, +0.018, +0.003, -0.049, -0.025), paired t p = 0.20, Wilcoxon p = 0.31: no significant difference.
- **Interpretation (hypotheses, not tested):** the fusion model barely uses the questionnaire (flat across hidden rates although the questionnaire alone gives 0.390). Possible causes: 1,280 image features vs 64 questionnaire features in the concat layer; whole questionnaire hidden in 30% of training samples; noisy checkpoint selection (3 of 5 fusion seeds kept a stage-1 checkpoint from epochs 0-2; validation has about 270 cases).
- **Next:** run `--fusion gated` and `film`, and `--no-dropout` (E2); consider a larger validation signal (e.g. selection on validation loss or a smoothed macro-F1) - to decide, not changed now. The image-only ablation (sampler, MobileNetV3) is still to run.
- **Docs:** thesis 5.8 / paper 3.8 rewritten for `LateFusionNet` and the staged training of the fusion model, plus the gated and FiLM variants (references: Arevalo et al. 2017, Perez et al. 2018); new thesis 8.2 / paper 4.2 with Table 8.2 / Table 2 and the paired tests (paired test and p-value defined; reference: Student 1908).

## 2026-10-09: Questionnaire-only baseline (Task 3.1, E1 arm 2) - first real results

- **Done:** `ml/models/q_model.py` (`QuestionnaireMLP`: [q_vec (40), q_mask (6)] -> 2 hidden layers of 64, ReLU, dropout 0.2 -> 4 logits) and `ml/run_q_only.py` (same cases, splits, seeds 0-4, class-weighted CE, early stopping on validation macro-F1 with patience 20, engine + evaluate.py; no image is read). Config block `q_baseline` in `configs/base.yaml`. `run_image_only.aggregate_seeds` now also groups by `missing_pct` (before, missing-answer rates would have been averaged together). 5 new tests (78 pass).
- **Fairness of comparison:** the test split is scored at r = 0, 0.25, 0.5, 0.75, 1 hidden answers with the same generator use, batch size and case order as the fusion evaluation in `train.py`, so both models see exactly the same hidden answers (tested).
- **Results (test, 5 seeds, mean ± sd):** macro-F1 0.390 ± 0.038, balanced accuracy 0.443 ± 0.043, accuracy 0.476 ± 0.048, ECE 0.083 ± 0.020, AURC 0.465 ± 0.040. Per class F1: eczema_dermatitis 0.569, normal_other 0.429, redness_rosacea 0.343 (about 6 test cases), acne 0.218. Hidden answers: 0.390 / 0.325 / 0.264 / 0.221 / 0.145 at 0 / 25 / 50 / 75 / 100%; at 100% one class is predicted for every case and balanced accuracy is exactly 0.250 (chance), as the mask design intends. eFST: I-II 0.401 ± 0.045 (117 cases), III-IV 0.342 ± 0.100 (120), V-VI 0.475 ± 0.131 (23); worst group III-IV x3, I-II x2 (mean 0.319); V-VI value is not an advantage (small group, spread larger than the gaps). Best epochs 16-51, 6-11 s per seed. Run folder: `ml/runs/e1_questionnaire_only/weighted_loss/` (git-ignored).
- **Decisions:** no field dropout in this plain baseline (`--p-field-drop` available for a robustness variant); weighted loss like the default image arm.
- **Docs:** method paragraph in thesis 5.8 / paper 3.8 (MLP, ReLU, dropout defined); new thesis 8.1 and paper 4.1 with Table 8.1 / Table 1; reference: Goodfellow et al. 2016.

## 2026-10-09: Fitzpatrick17k data-use terms

- **Fact:** the full Fitzpatrick17k images were requested from the authors; the agreement requires deleting them once the research is complete.
- **Decision:** Fitzpatrick17k (and DDI) are used for testing only, never for training, never redistributed, never shown in the app, repo, thesis or paper; only aggregate metrics are reported. The shipped model is trained on SCIN only, so the deletion obligation does not touch it.
- **Open:** reread the signed text for clauses on derived data/models and publication; note the deletion deadline; check commercial-use terms of SCIN and of any pretrained weights (ImageNet, PanDerm, DermLIP) before a public release. Not legal advice.
- **Docs:** one paragraph added to thesis 5.11 and paper 3.10; `data_sources.csv` note.

## 2026-10-09: External test sets and foundation-model linear probe (Task 2.5)

- **Done:** `ml/external_datasets.py`: `DDIDataset` and `Fitzpatrick17kDataset` (items shaped like SCIN items), label mapping through `label_map.yaml` plus a new `external_aliases` section (not read by `build_labels.py`; SCIN labels unchanged), a per-row status report (`mapped`, `excluded_class`, `unmapped`, `qc_wrong_label`, `missing_image`; only `mapped` rows are used), zero-shot inference of every SCIN image-only checkpoint, `external_eval.csv` in the evaluate.py format (split = dataset, seed = SCIN seed, plus logits and probabilities) and evaluate.py on it. `ml/foundation_probe.py`: frozen encoder from `timm:`, `open_clip:` or `hf:` (local weights for timm, e.g. PanDerm; DermLIP through OpenCLIP), features of all 1,809 used SCIN cases cached once, per seed a linear layer (multinomial logistic regression, standardised features, class-weighted CE, L2 penalty chosen on validation macro-F1), predictions + evaluate.py + `foundation_probe_test.csv` (mean ± sd). 8 new tests (73 pass).
- **Data facts:** Fitzpatrick17k (CSV checked): 16,577 rows, 114 labels; 4,012 map to targets (normal_other 1,892, mostly psoriasis; eczema_dermatitis 1,009; acne 857; redness_rosacea 254), 4,183 to non-target categories, 8,376 unmapped, 6 dropped by the quality check ("wrongly labelled"). Licence CC BY-NC-SA 3.0. DDI: 656 images, biopsy-confirmed, tones 12/34/56 mapped to eFST 1/3/5 (= groups I-II/III-IV/V-VI); download through Stanford AIMI / Redivis, licence still TO VERIFY. `data_sources.csv` updated.
- **Found:** the DermaAmin image URLs (about 90% of the mapped Fitzpatrick17k rows) return HTTP 404; only Atlas Dermatológico links work. The full image set must be requested from the authors (form in the Fitzpatrick17k repo). The downloader no longer retries 4xx answers and logs progress. DDI disease strings are not verified yet (aliases marked VERIFY; unmatched strings are listed in the report).
- **Decisions:** never guess a mapping (unknown -> dropped and reported); the probe uses the primary image without augmentation (frozen features); the L2 grid goes from 0 to 100 because a smoke run on EfficientNet-B0 features picked the edge of a narrower grid (a warning now flags edge choices); the checkpoint backbone is read from the run's `config_used.yaml`.
- **Checked:** end-to-end smoke tests (21 Atlas images, two 2-batch checkpoints; probe with `timm:efficientnet_b0` features on seeds 0-1); numbers meaningless, not recorded.
- **Docs:** new thesis 5.11 and paper 3.10 (zero-shot external evaluation, domain shift, mapping statuses, foundation models, frozen features, linear probe, standardisation, L2 penalty); references: Daneshjou et al. 2022, Groh et al. 2021, Alain and Bengio 2016, Radford et al. 2021, PanDerm (Yan et al. 2025), Derm1M/DermLIP (Yan et al. 2025).
- **Download result:** 619 of the 4,012 mapped Fitzpatrick17k images are still online (all from Atlas Dermatológico; 3,393 failed): normal_other 362, acne 126, eczema_dermatitis 115, redness_rosacea 16; FST 1: 12, 2: 100, 3: 165, 4: 194, 5: 97, 6: 32, unknown 19. Too few and too skewed (redness_rosacea 16) for a fair test, so the full set is still needed.
- **Next:** request the Fitzpatrick17k images and download DDI; check DDI disease strings against the report; get PanDerm weights; `pip install open_clip_torch` for DermLIP.

## 2026-10-09: Bug fixes in evaluate.py and train.py

- **evaluate.py:** `across_seeds` filtered rows with the pattern `worst=|-`, meant to drop the worst-group and gap rows, but every tone group name contains "-" (I-II, III-IV, 1-3, ...), so the across-seed summary in `metrics_summary.json` kept only the overall and "missing" rows. It now drops rows whose group starts with `worst=` and the `gap_macro_f1` metric only. Regression test added in `ml/tests/test_metrics.py` (65 tests pass). No reported numbers were affected (no real results exist yet).
- **train.py:** before stage 1, a `best_model.pt` left in the run folder by an earlier run with the same name was loaded, so a rerun silently started from the old weights instead of ImageNet. The file is now deleted at the start of each run (`run_image_only.py` already did this).
- **Process:** new standing rule: bugs are always repaired, even when a task says not to change a file.
- **Docs:** the thesis and paper already describe the intended behaviour (5.10 / 3.9), so no text change was needed.

## 2026-10-09: Multi-seed image-only baseline and imbalance ablation (Task 2.4, E1 arm 1)

- **Done:** `ml/run_image_only.py` trains `SkinImageBaseline` with the three-stage recipe on split seeds 0-4 (engine and evaluate.py are imported, not changed), keeps the best-validation checkpoint per seed (`seed_checkpoints/img_only_seed{seed}.pt`), writes val + test predictions, runs `evaluate.py` on the test split per seed and writes `e1_image_only_test.csv` (mean, sd, min, max and "mean ± sd" per metric, class and tone group). Options: `--backbone efficientnet_b0|mobilenetv3_large_100`, `--balance weighted_loss|sampler`, `--seeds`, `--skip-existing`; also callable as `run({...})` from a notebook. Tests in `ml/tests/test_run_image_only.py` (64 pass in total).
- **Ablation:** `weighted_loss` = inverse-frequency class weights in cross-entropy, uniform shuffling. `sampler` = plain cross-entropy + `WeightedRandomSampler` (weight 1 / class count, with replacement, epoch size = training-set size). Never both. Seed-0 training counts: eczema_dermatitis 748, normal_other 387, acne 101, redness_rosacea 30.
- **Found and handled:** the dataset's random image/augmentation draw depends on (seed, epoch, case), so a rare case drawn about 10 times in one epoch by the sampler (up to 16 in a check) would have been 10 identical copies. Repeated draws are now numbered and each repeat gets its own image and augmentation; the first draw equals the weighted-loss arm's draw (tested), so only the correction differs.
- **Found, not fixed (outside this task):** in `evaluate.py`, `across_seeds` drops every group whose name contains "-", which removes all tone groups (I-II, 1-3, ...). The new runner does its own across-seed summary from the per-seed `metrics_summary.csv`, so E1 is not affected; the fix in `evaluate.py` is pending.
- **Decision:** the winning arm is chosen by mean validation macro-F1, never by test results.
- **Checked:** smoke runs (1 epoch per stage, 2-3 batches, seeds 0-1) of both arms with EfficientNet-B0 and one MobileNetV3 run, plus `--skip-existing`; numbers meaningless, not recorded. Sampler check: about 25% of draws per class.
- **Docs:** thesis 5.8 and paper 3.8 extended (seeds, mean ± sd, class imbalance, ablation, the two corrections, repeated-draw handling, overfitting risk); references: Buda et al. 2018, PyTorch WeightedRandomSampler docs.
- **Next:** run the four full combinations (2 backbones x 2 balances, about 20 training runs) and record the results.

## 2026-10-08: Evaluation harness (Task 2.3)

- **Done:** `ml/src/skinconcern/metrics.py` extended (macro-F1, balanced accuracy, per-class precision/recall/F1 via sklearn; ECE with configurable bins and a reliability table; risk-coverage table and AURC; case-level bootstrap CI for any metric; eFST/eMST grouping) and new `ml/evaluate.py` (reads a predictions CSV, evaluates every split x seed x missing_pct slice, overall and per eFST/eMST group, worst group, across-seed mean/sd/min/max; writes `metrics_summary.json`, `metrics_summary.csv`, `risk_coverage.csv`). Tests in `ml/tests/test_metrics.py` (60 tests pass in total).
- **Wiring:** `engine.evaluate` now returns the confidence (max softmax) and eMST; the dataset item carries eMST. `train.py` writes `predictions.csv` (best model on validation, and on test at every missing rate) in the standard format and runs `evaluate.py` on it; the old per-rate CSVs are replaced by the harness outputs.
- **Decisions:** bootstrap resamples `case_id` (all rows of a drawn case kept). Worst group: only tone groups with at least 20 cases are eligible ("missing" is never a tone group); excluded small groups are listed. ECE uses 15 equal-width bins. A fast numpy path computes the bootstrap metrics from the confusion matrix; a test checks it equals the sklearn definitions. Duplicate case rows within a slice are rejected.
- **Checked:** a 2-epoch fusion smoke run produced all files end to end (numbers not recorded).
- **Docs:** thesis 5.10 and paper 3.9 extended (per-class metrics, calibration/ECE, risk-coverage/AURC, worst group on eFST and eMST, case-level bootstrap, across-seed summary); references: Guo et al. 2017, Geifman and El-Yaniv 2017, Sagawa et al. 2020.

## 2026-10-08: Staged fine-tuning of the image-only baseline (Task 2.2)

- **Done:** `ml/models/image_model.py` (`SkinImageBaseline`: timm EfficientNet-B0 or MobileNetV3, `set_stage(1|2|3)`, `get_optimizer_param_groups(base_lr)`), wired into `train.py --model image_only [--backbone ...] [--stages 1,2]`. Config block `image_baseline` in `configs/base.yaml`. Tests in `ml/tests/test_image_model.py` (8; 51 in total pass).
- **Recipe:** stage 1 head only (lr 1e-3, 5 epochs); stage 2 head + neck + top 2 blocks (head 3e-4, backbone 3e-5, 15 epochs); stage 3 optional, all layers (1e-4 / 1e-5, 10 epochs). Each stage reloads the best checkpoint so far and has its own early-stopping patience. `log.csv` records the stage, both learning rates and the number of trainable parameters.
- **Design decisions:** the backbone is handled as units `stem`, `blocks.0..K`, `neck` (EfficientNet: conv_head + bn2; MobileNetV3: conv_head after pooling), which works for both timm families. Frozen BatchNorm layers stay in eval mode so ImageNet statistics are not overwritten (tested: stage 1 leaves the whole backbone state unchanged). Biases and norm weights get no weight decay.
- **Found:** timm's default head init for these models scales by fan-out (4 outputs), giving a start loss of about 4.5 instead of about ln 4 = 1.4. The new head is initialised with std 0.01; start loss is now 1.28 and early validation macro-F1 rises faster. Smoke runs only (1-2 epochs per stage), numbers not recorded.
- **Open (important for RQ1):** the fusion model still trains in one phase with all layers open. For a fair comparison it must use the same staged recipe; planned for the fusion task.
- **Docs:** thesis 5.8 and paper 3.8 extended (backbones, staged fine-tuning, catastrophic forgetting, frozen BatchNorm, head init); reference: MobileNetV3 (Howard et al. 2019).

## 2026-10-08: Review of the whole ML pipeline (fixes and improvements)

- **Leakage found and fixed:** MD5 hashes of all 4,089 downloaded images (all 3,886 of the used cases) show 5 groups of 2-3 cases (12 cases) sharing identical photos, most likely resubmissions. In the old seed-0 split four such photos were in different splits. New `ml/scripts/find_duplicate_images.py` writes `ml/splits/duplicate_image_groups.csv`; `make_splits.py` now splits on these groups, and `test_no_leakage.py` checks it. New sizes: 3,522-3,525 / 754-757 / 754-756 per seed; used cases for seed 0: 1,266 / 273 / 270. One group has the same photos labelled redness_rosacea, eczema_dermatitis and excluded (label noise, kept and reported).
- **Images were distorted:** most SCIN photos are portrait 3:4 (median 810x1080, some 0.45:1); `Resize(224,224)` stretched them. Now letterbox (`LongestMaxSize` + black `PadIfNeeded`) for every split.
- **Model inference bug:** with no questionnaire the model sent zeros and an "answered" flag, unlike training. `FusionClassifier` now takes `q_vec` and `q_mask`; a missing questionnaire is zero features + all-ones mask, the same as in training. The old availability flag and in-model dropout were removed (answers are hidden in `train.py`). Grad-CAM wrapper updated.
- **Evaluation matched the text only partly:** the 25/50/75% test hid whole questionnaires per case, while the thesis says fields. It now hides each field with probability r (on top of natural missingness); r = 1 hides all.
- **Metrics:** per-group macro-F1 over the classes present in that group; 95% bootstrap CI (1,000 resamples) for every group; the tone gap now excludes the "missing" eFST group.
- **Focal loss:** weighted mean now divides by the summed target weights, like `nn.CrossEntropyLoss(weight)`, so gamma = 0 gives exactly the weighted CE (tested).
- **Smaller fixes:** `log.csv` logged the next epoch's learning rate; `get_dataloaders` accepts a config dict (no temp files); a warning lists cases with no image file; `results.json` reports failed images.
- **Speed:** a profile showed Windows re-spawning DataLoader workers each epoch (about 6 s per worker), not image decoding, was the bottleneck. The epoch counter is now a shared-memory tensor, so persistent workers keep the per-epoch image draw (tested). Plus a 448 px lossless image cache (`scripts/resize_image_cache.py`). Epoch time dropped from 62 s to 5 s after a one-time start; epoch-0 numbers are identical with and without the change.
- **Checked and unchanged:** label derivation, questionnaire encoding, audit numbers, stratification logic, engine AMP/early stopping. Considered, not changed: 35 used cases whose first dermatologist rated the image quality insufficient (they still have labels from the weighted label; 1.9%).
- **Docs:** thesis 5.6-5.10 and paper 3.6-3.9 updated (new split numbers, duplicate grouping, letterbox, missing-questionnaire representation, field-level hiding, bootstrap CIs; reference: Efron and Tibshirani 1993). `ml/README.md` now lists the pipeline order. 43 tests pass.

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
