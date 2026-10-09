"""Fusion model (Task 3.2): rewrite the fusion description in thesis 5.8 / paper 3.8 and add the gated / FiLM variants."""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocEditor  # noqa: E402

GMU = ("https://arxiv.org/abs/1702.01992",
       "J. Arevalo, T. Solorio, M. Montes-y-Gómez, F. A. González, Gated Multimodal Units for Information Fusion, "
       "ICLR Workshop 2017")
FILM = ("https://arxiv.org/abs/1709.07871",
        "E. Perez, F. Strub, H. de Vries, V. Dumoulin, A. Courville, FiLM: Visual Reasoning with a General "
        "Conditioning Layer, AAAI 2018")

RO_ARCH = (
    "Modelul combină două ramuri printr-o fuziune târzie (late fusion), adică ramurile sunt procesate separat și "
    "informațiile lor se unesc abia înainte de decizia finală (`ml/models/fusion_model.py`, clasa `LateFusionNet`). "
    "Ramura de imagine este aceeași rețea ca la modelul doar cu imagine, EfficientNet-B0 [{effnet}] sau "
    "MobileNetV3-Large, din biblioteca timm [{timm}] cu ponderi preantrenate pe ImageNet (învățare prin transfer: "
    "rețeaua pornește de la ce a învățat deja pe un set mare de imagini și este reantrenată pe SCIN), fără stratul de "
    "clasificare; ieșirea ei este vectorul de trăsături obținut prin medierea hărților de activare (1.280 de valori). "
    "Ramura chestionarului este o rețea cu două straturi de câte 64 de unități, care primește vectorul de 40 de "
    "trăsături alăturat măștii de 6 valori (46 de numere). Dacă chestionarul lipsește complet, modelul primește "
    "trăsături 0 și toate valorile măștii egale cu 1, aceeași reprezentare ca la antrenare, deci un chestionar absent nu "
    "este confundat cu unul completat cu răspunsuri 0. În varianta de bază (concat), cele două ieșiri se concatenează "
    "și trec printr-un strat final care produce scorul pentru fiecare dintre cele patru categorii."
)
EN_ARCH = (
    "The model combines two branches by late fusion: the branches are processed separately and their information is "
    "joined only before the final decision (`ml/models/fusion_model.py`, class `LateFusionNet`). The image branch is "
    "the same network as in the photo-only model, EfficientNet-B0 [{effnet}] or MobileNetV3-Large, from the timm "
    "library [{timm}] with weights pretrained on ImageNet (transfer learning: the network starts from what it already "
    "learned on a large image set and is retrained on SCIN), without its classification layer; its output is the "
    "feature vector obtained by averaging the activation maps (1,280 values). The questionnaire branch is a network "
    "with two layers of 64 units that receives the 40-feature vector together with the 6-value mask (46 numbers). When "
    "the questionnaire is missing entirely, the model receives zero features and an all-ones mask, the same "
    "representation as in training, so an absent questionnaire is not confused with one answered with zeros. In the "
    "basic variant (concat), the two outputs are concatenated and passed to a final layer that scores each of the four "
    "categories."
)
RO_TRAIN = (
    "Pentru robustețea la răspunsuri lipsă se folosește modality dropout: în timpul antrenării, pentru fiecare exemplu "
    "chestionarul este ascuns în întregime cu probabilitate 0,3, iar fiecare câmp este ascuns separat cu probabilitate "
    "0,15. Un câmp ascuns primește trăsături 0 și masca 1, exact ca un răspuns lipsă real, deci modelul învață să se "
    "descurce și fără chestionar. Cum categoriile sunt dezechilibrate, pierderea (loss, măsura erorii pe care o "
    "minimizează antrenarea) este entropia încrucișată ponderată invers proporțional cu frecvența clasei. Modelul cu "
    "fuziune este antrenat cu exact aceleași trei etape ca modelul doar cu imagine (descrise mai jos), cu optimizatorul "
    "AdamW [{adamw}], descreștere cosinusoidală a ratei de învățare [{cos}] și precizie mixtă pe GPU, astfel încât "
    "singura diferență dintre cele două modele este chestionarul. Ramura chestionarului și straturile de fuziune sunt "
    "noi, deci se antrenează în toate etapele, cu rata stratului de clasificare. Se păstrează punctul de control "
    "(checkpoint) cu cel mai bun macro-F1 pe setul de validare."
)
EN_TRAIN = (
    "For robustness to missing answers we use modality dropout: during training, the whole questionnaire is hidden for "
    "a sample with probability 0.3, and each field is hidden independently with probability 0.15. A hidden field gets "
    "features 0 and mask 1, exactly like a real missing answer, so the model learns to work without the questionnaire. "
    "Because the categories are imbalanced, the loss (the error measure that training minimises) is cross-entropy "
    "weighted inversely to class frequency. The fusion model is trained with exactly the same three stages as the "
    "photo-only model (described below), with the AdamW optimiser [{adamw}], cosine learning-rate decay [{cos}] and "
    "mixed precision on GPU, so the questionnaire is the only difference between the two models. The questionnaire "
    "branch and the fusion layers are new, so they train in every stage at the classification-layer rate. The "
    "checkpoint with the best validation macro-F1 is kept."
)
RO_VARIANTS = (
    "Pe lângă concatenare, sunt implementate două variante de fuziune mai puternice, care permit chestionarului să "
    "influențeze felul în care este folosită imaginea. (1) Fuziunea cu poartă (gated multimodal unit) [{gmu}]: ambele "
    "ramuri sunt proiectate la aceeași dimensiune (256), iar o poartă, adică un vector de valori între 0 și 1 calculat "
    "din ambele ramuri, decide pentru fiecare dimensiune cât provine din imagine și cât din chestionar. Când masca arată "
    "că lipsesc răspunsurile, poarta poate învăța să se bazeze pe fotografie; valoarea medie a porții poate fi "
    "inspectată pentru fiecare caz. (2) Condiționarea de tip FiLM (Feature-wise Linear Modulation) [{film}]: "
    "chestionarul produce doi vectori, γ și β, care scalează și deplasează fiecare trăsătură a imaginii (f' = f·(1 + γ) "
    "+ β). γ și β pornesc de la 0, deci la începutul antrenării modelul se comportă exact ca modelul doar cu imagine. "
    "Varianta este aleasă din configurație (`fusion.variant`), iar modelele antrenate sunt salvate ca "
    "`fusion_late_<variantă>_seed<k>.pt` de scriptul `ml/run_fusion.py`."
)
EN_VARIANTS = (
    "Besides concatenation, two stronger fusion variants are implemented, which let the questionnaire influence how "
    "the image is used. (1) Gated fusion (gated multimodal unit) [{gmu}]: both branches are projected to the same size "
    "(256), and a gate, a vector of values between 0 and 1 computed from both branches, decides for every dimension how "
    "much comes from the image and how much from the questionnaire. When the mask shows that answers are missing, the "
    "gate can learn to rely on the photo; the mean gate value can be inspected for each case. (2) FiLM-style "
    "conditioning (Feature-wise Linear Modulation) [{film}]: the questionnaire produces two vectors, γ and β, that scale "
    "and shift every image feature (f' = f·(1 + γ) + β). γ and β start at 0, so at the start of training the model "
    "behaves exactly like the photo-only model. The variant is chosen in the configuration (`fusion.variant`), and the "
    "trained models are saved as `fusion_late_<variant>_seed<k>.pt` by `ml/run_fusion.py`."
)


def ref_no(ed: DocEditor, needle: str) -> int:
    import re
    refs = [p.text for p in ed.doc.paragraphs if re.match(r"^\[\d+\]", p.text.strip())]
    return next(i for i, r in enumerate(refs, 1) if needle in r)


for path, arch, train_txt, variants, start_arch, start_train, section in (
        ("Teza_Licenta.docx", RO_ARCH, RO_TRAIN, RO_VARIANTS, "Modelul combină", "Pentru robustețea",
         "5.8 Modelul și fuziunea multimodală"),
        ("Paper_Skin_Concern.docx", EN_ARCH, EN_TRAIN, EN_VARIANTS, "The model combines", "For robustness",
         "3.8 Model and training")):
    ed = DocEditor(str(ROOT / "docs" / path))
    if any("LateFusionNet" in p.text for p in ed.doc.paragraphs):
        print(path, "already updated")
        continue
    n = {"effnet": ref_no(ed, "EfficientNet"), "timm": ref_no(ed, "timm"), "adamw": ref_no(ed, "Weight Decay"),
         "cos": ref_no(ed, "SGDR"), "gmu": ed.add_reference(GMU[1], GMU[0]), "film": ed.add_reference(FILM[1], FILM[0])}
    p_arch = next(p for p in ed.doc.paragraphs if p.text.startswith(start_arch))
    p_train = next(p for p in ed.doc.paragraphs if p.text.startswith(start_train))
    # rebuild the two paragraphs so `code` spans get the code font
    ed.body_paragraph_before(p_arch, arch.format(**n))
    p_arch._p.getparent().remove(p_arch._p)
    ed.body_paragraph_before(p_train, train_txt.format(**n))
    p_train._p.getparent().remove(p_train._p)
    ed.append_to_section(section, [variants.format(**n)])
    try:
        ed.save()
        print(path, "updated")
    except PermissionError:
        print(path, "LOCKED (open in Word) - not updated")
