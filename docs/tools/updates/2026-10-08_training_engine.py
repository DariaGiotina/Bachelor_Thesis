"""Add engine details (loss options, early stopping, mixed precision) to thesis 5.8 and paper 3.8."""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocEditor  # noqa: E402

FOCAL = "https://arxiv.org/abs/1708.02002"
REF = ("T.-Y. Lin, P. Goyal, R. Girshick, K. He, P. Dollár, Focal Loss for Dense Object Detection, "
       "ICCV 2017")

RO = ("Antrenarea este realizată de un motor reutilizabil (ml/engine.py) care nu depinde de arhitectura modelului: "
      "aceleași funcții de antrenare și evaluare servesc atât modelul doar cu imagine, cât și modelul cu fuziune. Funcția "
      "de pierdere poate fi entropia încrucișată ponderată pe clase sau pierderea focală (focal loss) [{n}], care reduce "
      "contribuția exemplelor ușoare, sigure, pentru ca antrenarea să se concentreze pe cele dificile și rare; cele două "
      "variante se compară ca ablație. Antrenarea folosește precizie mixtă automată (AMP), adică calcule în precizie "
      "redusă pe GPU pentru viteză. Criteriul de oprire și de salvare a punctului de control este macro-F1 pe validare, "
      "nu acuratețea simplă, care ar fi înșelătoare la clase dezechilibrate; antrenarea se oprește timpuriu (early "
      "stopping) dacă macro-F1 nu se îmbunătățește timp de 5 epoci consecutive. Pentru fiecare epocă se înregistrează "
      "pierderea de antrenare, pierderea de validare, macro-F1 și durata (fișierul log.csv).")
EN = ("Training is run by a reusable engine (ml/engine.py) that does not depend on the model architecture: the same "
      "training and evaluation functions serve both the photo-only and the fusion model. The loss can be class-weighted "
      "cross-entropy or focal loss [{n}], which down-weights easy, confident examples so training concentrates on hard "
      "and rare ones; the two are compared as an ablation. Training uses automatic mixed precision (AMP), i.e. "
      "reduced-precision arithmetic on the GPU for speed. Early stopping and checkpointing use validation macro-F1, "
      "not plain accuracy, which would be misleading with imbalanced classes; training stops early if macro-F1 does not "
      "improve for 5 consecutive epochs. For every epoch the training loss, validation loss, macro-F1 and epoch time are "
      "logged (log.csv).")

for path, head, text in (("Teza_Licenta.docx", "5.8 Modelul și fuziunea multimodală", RO),
                         ("Paper_Skin_Concern.docx", "3.8 Model and training", EN)):
    ed = DocEditor(str(ROOT / "docs" / path))
    n = ed.add_reference(REF, FOCAL)
    marker = text[:40]
    if not any(p.text.startswith(marker) for p in ed.doc.paragraphs):
        ed.append_to_section(head, [text.format(n=n)])
    try:
        ed.save()
        print(path, "updated")
    except PermissionError:
        print(path, "LOCKED (open in Word) - not updated")
