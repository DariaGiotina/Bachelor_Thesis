"""Add the multi-seed image-only run (E1 arm 1) and the imbalance ablation to thesis 5.8 / paper 3.8."""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocEditor  # noqa: E402

BUDA = ("https://arxiv.org/abs/1710.05381",
        "M. Buda, A. Maki, M. A. Mazurowski, A systematic study of the class imbalance problem in convolutional "
        "neural networks, Neural Networks 106, 2018")
WRS = ("https://docs.pytorch.org/docs/stable/data.html#torch.utils.data.WeightedRandomSampler",
       "PyTorch documentation, torch.utils.data.WeightedRandomSampler")

RO = [
    "Modelul de referință doar cu imagine reprezintă primul braț al experimentului E1 și este rulat de scriptul "
    "`ml/run_image_only.py` pe toate cele cinci variante de împărțire (seed-urile 0–4). Un seed este numărul care "
    "inițializează generatorul de numere aleatoare; fiecare seed are propria împărțire pe cazuri, propria ordine a "
    "exemplelor și propria augmentare, deci repetarea pe cinci seed-uri arată cât de mult variază rezultatul doar din "
    "cauza hazardului. Pentru fiecare seed se antrenează modelul în cele trei etape, se păstrează punctul de control "
    "(checkpoint, adică ponderile salvate ale rețelei) cu cel mai bun macro-F1 pe validare, iar acesta este testat o "
    "singură dată. Predicțiile de test sunt evaluate cu `ml/evaluate.py`, iar rezultatele celor cinci seed-uri sunt "
    "raportate ca medie ± abatere standard (abaterea standard măsoară cât de împrăștiate sunt cele cinci valori în "
    "jurul mediei), în fișierul `e1_image_only_test.csv`.",
    "Dezechilibrul claselor înseamnă că unele categorii au mult mai multe exemple decât altele: în setul de antrenare "
    "al seed-ului 0 sunt 748 de cazuri eczema_dermatitis, 387 normal_other, 101 acne și doar 30 redness_rosacea. Fără "
    "corecție, rețeaua ar învăța în principal clasa majoritară. Două corecții uzuale [{buda}] sunt comparate printr-un "
    "studiu de ablație (ablation study), adică un experiment în care se schimbă o singură componentă și restul rămâne "
    "identic, pentru a vedea efectul acelei componente. (a) Pierderea ponderată pe clase: entropia încrucișată primește "
    "pentru fiecare clasă o pondere invers proporțională cu frecvența ei (numărul total de cazuri împărțit la numărul de "
    "clase înmulțit cu numărul de cazuri ale clasei; la seed-ul 0, de exemplu, 10,6 pentru redness_rosacea și 0,42 "
    "pentru eczema_dermatitis), iar exemplele sunt parcurse în ordine aleatoare, fiecare o dată pe epocă. (b) "
    "Eșantionarea ponderată (WeightedRandomSampler [{wrs}]): pierderea nu este ponderată, dar cazurile sunt extrase cu "
    "înlocuire (același caz poate fi extras de mai multe ori în aceeași epocă) cu probabilitatea invers proporțională cu "
    "numărul de cazuri al clasei lor, astfel încât fiecare clasă ocupă în medie un sfert din extrageri. Cele două "
    "corecții nu sunt folosite niciodată împreună, deoarece ar compensa dezechilibrul de două ori.",
    "La eșantionarea ponderată, un caz rar este extras de aproximativ zece ori pe epocă (redness_rosacea: 30 de cazuri "
    "pentru circa 316 extrageri). Deoarece imaginea și augmentarea unui caz depind de seed, de epocă și de caz, toate "
    "copiile ar fi fost identice; scriptul numerotează extragerile repetate și fiecare repetare primește propria imagine "
    "a cazului (dacă are mai multe) și propria augmentare. Prima extragere rămâne identică cu cea din varianta (a), deci "
    "singura diferență dintre cele două variante este metoda de corecție. Riscul cunoscut al eșantionării este "
    "supraînvățarea (overfitting) pe puținele cazuri rare, adică memorarea lor în locul învățării unor trăsături "
    "generale; validarea pe macro-F1 și oprirea timpurie limitează acest risc. Ablația se rulează pentru ambele rețele "
    "(EfficientNet-B0 și MobileNetV3-Large), iar varianta cu cel mai bun macro-F1 mediu pe validare devine referința "
    "doar cu imagine din E1.",
]
EN = [
    "The photo-only baseline is the first arm of experiment E1 and is run by `ml/run_image_only.py` on all five split "
    "variants (seeds 0-4). A seed is the number that initialises the random number generator; each seed has its own "
    "case-level split, sample order and augmentation, so repeating the run over five seeds shows how much the result "
    "varies by chance alone. For every seed the model is trained in the three stages, the checkpoint (the saved network "
    "weights) with the best validation macro-F1 is kept, and it is tested once. Test predictions are scored by "
    "`ml/evaluate.py`, and the five seeds are reported as mean ± standard deviation (the standard deviation measures how "
    "far the five values spread around their mean) in `e1_image_only_test.csv`.",
    "Class imbalance means that some categories have many more examples than others: the seed-0 training set has 748 "
    "eczema_dermatitis, 387 normal_other, 101 acne and only 30 redness_rosacea cases. Without a correction the network "
    "would mainly learn the majority class. Two common corrections [{buda}] are compared in an ablation study, i.e. an "
    "experiment that changes one component and keeps everything else identical, to isolate that component's effect. (a) "
    "Class-weighted loss: cross-entropy gives each class a weight inversely proportional to its frequency (the total "
    "number of cases divided by the number of classes times the class's case count; for seed 0, e.g., 10.6 for "
    "redness_rosacea and 0.42 for eczema_dermatitis), and the cases are visited in random order, each once per epoch. "
    "(b) Weighted sampling (WeightedRandomSampler [{wrs}]): the loss is unweighted, but cases are drawn with replacement "
    "(the same case can be drawn several times in one epoch) with probability inversely proportional to the case count of "
    "their class, so each class makes up about a quarter of the draws. The two corrections are never combined, as that "
    "would correct the imbalance twice.",
    "With weighted sampling a rare case is drawn about ten times per epoch (redness_rosacea: 30 cases for about 316 "
    "draws). Because the image and augmentation of a case depend on the seed, the epoch and the case, all copies would "
    "have been identical; the script numbers repeated draws and each repeat gets its own image of the case (if it has "
    "several) and its own augmentation. The first draw is identical to the one in variant (a), so the correction method "
    "is the only difference between the two arms. The known risk of oversampling is overfitting to the few rare cases, "
    "i.e. memorising them instead of learning general features; validation on macro-F1 and early stopping limit this "
    "risk. The ablation is run for both networks (EfficientNet-B0 and MobileNetV3-Large), and the variant with the best "
    "mean validation macro-F1 becomes the photo-only reference in E1.",
]

for path, head, paras in (("Teza_Licenta.docx", "5.8 Modelul și fuziunea multimodală", RO),
                          ("Paper_Skin_Concern.docx", "3.8 Model and training", EN)):
    ed = DocEditor(str(ROOT / "docs" / path))
    if any("run_image_only.py" in p.text for p in ed.doc.paragraphs):
        print(path, "already updated")
        continue
    n = {k: ed.add_reference(t, u) for k, (u, t) in {"buda": BUDA, "wrs": WRS}.items()}
    ed.append_to_section(head, [t.format(**n) for t in paras])
    try:
        ed.save()
        print(path, "updated")
    except PermissionError:
        print(path, "LOCKED (open in Word) - not updated")
