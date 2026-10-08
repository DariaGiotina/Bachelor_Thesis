"""Add the data-loading / augmentation section to Teza_Licenta.docx and Paper_Skin_Concern.docx.

Inserts a new section before the model section, renumbers the later headings and the static
table-of-contents lines. Page numbers in the contents update when the fields are refreshed in Word.
"""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocEditor  # noqa: E402

# ------------------------------------------------------------------ thesis (RO)
T_NEW = "5.7 Încărcarea datelor, selecția imaginilor și augmentarea"
T_OLD = [("5.9 Protocolul de evaluare", "5.10 Protocolul de evaluare"),
         ("5.8 Explicabilitate (Grad-CAM)", "5.9 Explicabilitate (Grad-CAM)"),
         ("5.7 Modelul și fuziunea multimodală", "5.8 Modelul și fuziunea multimodală")]
T_PARAS = [
    "Pentru antrenare, datele sunt furnizate modelului printr-o clasă `SCINDataset` (fișierul `ml/data_loading.py`), "
    "care, pentru fiecare `case_id`, returnează un set de tensori (tablouri numerice folosite de PyTorch): imaginea, "
    "vectorul chestionarului (`q_vec`, 40 de valori), masca de valori lipsă (`q_mask`, 6 valori, câte una pe câmp), "
    "categoria țintă ca număr întreg (`label`), tipul de piele eFST (`eFST`, cu −1 când lipsește) și identificatorul "
    "cazului. Încărcătorul de date (DataLoader) grupează cazurile în loturi (batch-uri) de 32 de exemple, adică "
    "grupuri de exemple procesate împreună de model la un pas de antrenare. Cele cinci categorii definite în secțiunea "
    "5.4 sunt reduse la patru clase de antrenare: grupa `excluded` (cazuri cu etichetă ambiguă, sub prag sau fără "
    "etichetă) nu este o categorie-țintă a asistentului și este lăsată deoparte. Rămân 1.809 cazuri, repartizate pentru "
    "seed-ul 0 astfel: 1.266 în antrenare, 272 în validare și 271 în testare.",
    "Un caz poate avea până la trei fotografii. La antrenare, la fiecare epocă (o trecere completă prin setul de "
    "antrenare) se alege aleatoriu o singură imagine a cazului, pentru a crește varietatea imaginilor văzute de model. "
    "La validare și testare se folosește întotdeauna imaginea principală (`image_1_path`), astfel încât evaluarea să fie "
    "exact reproductibilă. Alegerea aleatorie este derivată din seed, epocă și indexul cazului, deci dă același rezultat "
    "indiferent de numărul de procese de încărcare. Dacă un fișier lipsește sau este corupt, se încearcă o altă imagine a "
    "aceluiași caz; dacă niciuna nu poate fi citită, se returnează o imagine neagră marcată prin `image_ok = 0`, iar "
    "antrenarea nu se oprește.",
    "Augmentarea înseamnă modificarea aleatorie a imaginilor de antrenare pentru ca modelul să nu memoreze exemplele "
    "și să se descurce la fotografii făcute în condiții diferite. Se aplică exclusiv pe setul de antrenare: oglindire "
    "orizontală (probabilitate 0,5), deplasare, scalare și rotire (deplasare până la 6%, scalare între 0,9 și 1,1, "
    "rotire până la 15°) și variație de culoare (luminozitate, contrast și saturație cu ±0,2, nuanță cu ±0,02). Variația "
    "nuanței este intenționat foarte mică, deoarece culoarea pielii este variabila pe care se măsoară echitatea și nu "
    "trebuie distorsionată. Toate seturile sunt redimensionate la 224×224 pixeli și normalizate cu media "
    "(0,485; 0,456; 0,406) și abaterea standard (0,229; 0,224; 0,225) ale setului ImageNet, valorile cu care au fost "
    "antrenate rețelele preantrenate; validarea și testarea nu primesc nicio augmentare în afară de aceste două operații. "
    "Parametrii se află în `ml/configs/base.yaml`, iar funcția `seed_everything` (`ml/utils/seed.py`) fixează "
    "generatoarele aleatorii din Python, NumPy și PyTorch pentru reproductibilitate.",
]

t = DocEditor(str(ROOT / "docs" / "Teza_Licenta.docx"))
if not t.has_heading(T_NEW):
    for old, new in T_OLD:
        t.rename_heading(old, new)
    anchor = t.heading("5.8 Modelul și fuziunea multimodală")
    t.heading_before(anchor, T_NEW, 2)
    for text in T_PARAS:
        t.body_paragraph_before(anchor, text)
    toc = t.toc_entries("5.8 Modelul și fuziunea multimodală")[0]
    t.add_toc_entry_before(toc, T_NEW, "12")
    t.replace_in_paragraph("Acest capitol descrie", "Secțiunile 5.1–5.6", "Secțiunile 5.1–5.7")
    t.replace_in_paragraph("Acest capitol descrie", "validare și testare (5.6).",
                           "validare și testare (5.6), încărcarea datelor și augmentarea (5.7).")
    t.replace_in_paragraph("Acest capitol descrie", "5.7–5.9", "5.8–5.10")
    try:
        t.save()
        print("thesis updated")
    except PermissionError:
        print("THESIS LOCKED (open in Word) - not updated")

# ------------------------------------------------------------------- paper (EN)
P_NEW = "3.7 Data loading and augmentation"
P_PARAS = [
    "Training data are served by a `SCINDataset` class (`ml/data_loading.py`) that returns, for each `case_id`, a "
    "set of tensors (numeric arrays used by PyTorch): the image, the questionnaire vector (`q_vec`, 40 values), the "
    "missingness mask (`q_mask`, 6 values, one per field), the target category as an integer (`label`), the "
    "eFST skin type (`eFST`, −1 when missing) and the case identifier. The DataLoader groups cases into batches of 32, "
    "i.e. groups of examples the model processes together in one training step. The five categories of Section 3.4 "
    "are reduced to four training classes: the `excluded` group (ambiguous, below-threshold or unlabelled cases) is not "
    "a target category of the assistant and is left out. This leaves 1,809 cases, split for seed 0 into 1,266 train, "
    "272 validation and 271 test cases.",
    "A case can have up to three photographs. During training, one image per case is drawn at random in every epoch "
    "(one full pass over the training set) to increase image variety. For validation and test the primary image "
    "(`image_1_path`) is always used, so evaluation is exactly reproducible. The random draw is derived from the seed, "
    "the epoch and the case index, so it does not depend on the number of loader processes. If a file is missing or "
    "corrupted, another image of the same case is tried; if none can be read, a black image flagged `image_ok = 0` is "
    "returned and training continues.",
    "Augmentation means randomly modifying training images so the model does not memorise examples and copes with "
    "photographs taken under different conditions. It is applied to the training split only: horizontal flip "
    "(probability 0.5), shift, scale and rotation (shift up to 6%, scale 0.9 to 1.1, rotation up to 15°) and colour "
    "jitter (brightness, contrast and saturation ±0.2, hue ±0.02). Hue jitter is deliberately tiny because skin colour "
    "is the variable fairness is measured on and must not be distorted. All splits are resized to 224×224 pixels and "
    "normalised with the ImageNet mean (0.485, 0.456, 0.406) and standard deviation (0.229, 0.224, 0.225), the "
    "statistics the pretrained networks were trained with; validation and test receive no augmentation beyond these two "
    "steps. Parameters are kept in `ml/configs/base.yaml`, and `seed_everything` (`ml/utils/seed.py`) fixes the random "
    "generators of Python, NumPy and PyTorch for reproducibility.",
]

p = DocEditor(str(ROOT / "docs" / "Paper_Skin_Concern.docx"))
if not p.has_heading(P_NEW):
    p.rename_heading("3.8 Evaluation protocol", "3.9 Evaluation protocol")
    p.rename_heading("3.7 Model and training", "3.8 Model and training")
    anchor = p.heading("3.8 Model and training")
    p.heading_before(anchor, P_NEW, 2)
    for text in P_PARAS:
        p.body_paragraph_before(anchor, text)
    try:
        p.save()
        print("paper updated")
    except PermissionError:
        print("PAPER LOCKED (open in Word) - not updated")
print("ok")
