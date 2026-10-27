#!/usr/bin/env bash
# Rerun every step behind the reported results, in order (Task 4.5).
#
#   bash run_all.sh            # everything (days on one RTX 3060: about 150 training runs)
#   bash run_all.sh data       # one stage: data | e1 | e2 | e5 | e7 | e4 | report | export | test
#
# Run from ml/ with the virtual environment active (README). Training steps skip arms whose
# checkpoints already exist, so an interrupted run can be restarted with the same command.
# Needs the datasets in data/ (git-ignored): SCIN downloads itself; Fitzpatrick17k (from the
# authors, research only) and DDI (Stanford, Redivis) must be placed by hand; PanDerm weights in
# data/models/panderm/ (from the authors); DermLIP needs `hf auth login` (gated model).
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-python}
SEEDS="0 1 2 3 4 5 6 7 8 9"
STAGE=${1:-all}
run() { echo "+ $*"; "$PY" "$@"; }
want() { [[ "$STAGE" == all || "$STAGE" == "$1" ]]; }

if want data; then
  run scripts/audit_scin.py --download
  run labels/build_labels.py
  run features/encode_questionnaire.py
  run scripts/download_scin_images.py --used-only --all-images
  run ood_detect.py --make-list
  run scripts/download_scin_images.py --case-ids labels/scin_near_ood.csv
  run scripts/resize_image_cache.py
  run scripts/resize_image_cache.py --src data/fitzpatrick17k_allData/finalfitz17k \
      --dst data/fitzpatrick17k_allData/images_448 --pattern "*.jpg"
  run scripts/find_duplicate_images.py
  run splits/make_splits.py
  run splits/make_fitzpatrick_splits.py
fi

if want e1; then  # RQ1: photo, questionnaire, fusion; then the method checks of the null result
  run run_e1.py --seeds $SEEDS --arms image_only questionnaire_only fusion_concat fusion_gated \
      fusion_film fusion_concat_nodrop ensemble_image_q
  run analysis/questionnaire_diagnostics.py
  run analysis/fusion_positive_control.py
  run run_stacking.py --seeds $SEEDS
  run analysis/stacking_synthetic_ceiling.py
  run run_e1.py --no-train --seeds $SEEDS --arms image_only questionnaire_only fusion_concat \
      stack_photo stack_photo_q stack_photo_qmlp stack_q --out-dir results/e1/stacking
  run external_datasets.py --checkpoints "runs/e1_image_only/efficientnet_b0_weighted_loss/seed_checkpoints/*.pt"
fi

if want e2; then  # RQ2: hidden answers, answer dropout
  run run_e2_dropout.py --seeds $SEEDS
  run eval_missingness.py
fi

if want e5; then  # frozen encoders + linear probe
  run run_e1.py --seeds $SEEDS --arms image_only probe_effb0 probe_vit_in21k probe_dinov2 \
      probe_panderm_base probe_panderm_large probe_dermlip --out-dir results/e5 --name e5
fi

if want e7; then  # extra Fitzpatrick17k training data (research only, checkpoints deleted with the images)
  run run_fitz_pooling.py --arms fitz_pooled fitz_pretrain --seeds $SEEDS
fi

if want e4; then  # RQ4: calibration, abstention, out-of-scope detector, Grad-CAM; RQ3 by tone
  run calibrate.py --export image_only fusion_film
  run run_e4.py
  run ood_detect.py
  run run_gradcam.py
  run analyze_fairness.py
fi

if want report; then
  run stats_tests.py
  run make_report_assets.py
fi

if want export; then
  run export_model.py
  run results_registry.py
fi

if want test; then
  run -m pytest -q
fi
