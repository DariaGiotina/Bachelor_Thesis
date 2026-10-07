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

Datasets (SCIN, DDI, Fitzpatrick17k) go in `ml/data/` (git-ignored).

Colab first cell:

```
!pip install -q timm grad-cam mediapipe fairlearn albumentations
from google.colab import drive; drive.mount('/content/drive')
```
