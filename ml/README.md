# ML environment

Informational skin-concern classifier (not a medical device).

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
pip install -r requirements.txt
pip install -e .
pytest
```

Datasets go in `ml/data/` (git-ignored). SCIN images must not be redistributed
(SCIN Data Use License).

## Pipeline (run from `ml/`, in this order)

| Step | Command | Output (committed unless noted) |
|---|---|---|
| 1. Metadata + audit | `python scripts/audit_scin.py --download` | `reports/scin_schema.json`, `reports/scin_audit_report.md` |
| 2. Target categories | `python labels/build_labels.py` | `labels/scin_labels.csv`, `labels/class_counts_by_tone.csv` |
| 3. Questionnaire encoding | `python features/encode_questionnaire.py` | `features/questionnaire_features.parquet` |
| 4. Images of the used cases (~3.9 GB) | `python scripts/download_scin_images.py --used-only --all-images` | `data/scin/images/` (ignored) |
| 5. Downscaled image cache | `python scripts/resize_image_cache.py` | `data/scin/images_448/` (ignored) |
| 6. Duplicate photos | `python scripts/find_duplicate_images.py` | `splits/duplicate_image_groups.csv` |
| 7. Splits (seeds 0-4) | `python splits/make_splits.py` | `splits/train_val_test_splits.json`, `splits/split_summary.csv` |
| 8. Sanity batch | `python data_loading.py` | `sanity_batch.png` (ignored: shows SCIN photos) |
| 9. Train + test | `python train.py --model fusion --seed 0` | `runs/<exp_name>/` (ignored) |
| 10. E1 image-only, seeds 0-4 | `python run_image_only.py --backbone efficientnet_b0 --balance weighted_loss` | `runs/e1_image_only/<backbone>_<balance>/` (ignored) |

`train.py --model` is `dummy` (pipeline check), `image_only` (photo-only baseline, staged fine-tuning,
`--backbone efficientnet_b0|mobilenetv3_large_100`, `--stages 1,2,3`) or `fusion` (photo + questionnaire). Each run writes `best_model.pt`, `log.csv`, `config_used.yaml`,
`results.json`, `predictions.csv` (one row per case: true/predicted category, confidence, eFST, eMST,
seed, share of hidden questionnaire fields) and, via `evaluate.py`, `metrics_summary.json`,
`metrics_summary.csv` and `risk_coverage.csv`.

`python evaluate.py <predictions.csv>` evaluates any predictions file (several seeds or missing rates
in one file are fine): macro-F1, balanced accuracy, accuracy and ECE with 95% case-level bootstrap
CIs, per-class precision/recall/F1, eFST and eMST groups, the worst tone group (>= 20 cases) and
risk-coverage / AURC.

`run_image_only.py` trains the photo-only baseline on every split seed and runs the imbalance
ablation: `--balance weighted_loss` (class-weighted cross-entropy) or `--balance sampler`
(unweighted cross-entropy + `WeightedRandomSampler`). It writes `seed_checkpoints/img_only_seed{seed}.pt`,
per-seed predictions and metrics, `seed_runs.csv` and `e1_image_only_test.csv` (test metrics across
seeds as mean ± sd). Run the four combinations (2 backbones x 2 balances); `--skip-existing` resumes.

Step 6 must run before step 7: cases that share an identical photo are kept in the same split.

Colab first cell:

```
!pip install -q timm grad-cam mediapipe fairlearn albumentations pyarrow
from google.colab import drive; drive.mount('/content/drive')
```
