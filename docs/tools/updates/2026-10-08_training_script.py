"""Fill thesis 5.8 / 5.10 and paper 3.8 / 3.9 with the model, training and evaluation method."""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocEditor  # noqa: E402

EFF = "https://arxiv.org/abs/1905.11946"
TIMM = "https://github.com/huggingface/pytorch-image-models"
ADAMW = "https://arxiv.org/abs/1711.05101"
COS = "https://arxiv.org/abs/1608.03983"

REFS = [
    ("M. Tan, Q. V. Le, EfficientNet: Rethinking Model Scaling for Convolutional Neural Networks, ICML 2019", EFF),
    ("R. Wightman, PyTorch Image Models (timm), GitHub repository", TIMM),
    ("I. Loshchilov, F. Hutter, Decoupled Weight Decay Regularization, ICLR 2019", ADAMW),
    ("I. Loshchilov, F. Hutter, SGDR: Stochastic Gradient Descent with Warm Restarts, ICLR 2017", COS),
]


def build(ed, lang):
    n = {u: ed.add_reference(t, u) for t, u in REFS}
    e, t_, a, c = (n[u] for u in (EFF, TIMM, ADAMW, COS))
    if lang == "ro":
        model = [
            f"Modelul combină două ramuri printr-o fuziune târzie (late fusion), adică ramurile sunt procesate separat și "
            f"informațiile lor se unesc abia înainte de decizia finală. Ramura de imagine este rețeaua EfficientNet-B0 [{e}], "
            f"preluată din biblioteca timm [{t_}] cu ponderi preantrenate pe ImageNet (învățare prin transfer: rețeaua pornește "
            f"de la ce a învățat deja pe un set mare de imagini și este reantrenată pe SCIN). Ramura chestionarului este o "
            f"rețea mică cu un strat de 64 de unități, care primește vectorul de 40 de trăsături alăturat măștii de 6 valori "
            f"(46 de numere). Ieșirile celor două ramuri se concatenează și trec printr-un strat final care produce scorul "
            f"pentru fiecare dintre cele patru categorii. Ca valoare de referință se antrenează și un model doar cu imagine, "
            f"fără ramura chestionarului.",
            "Pentru robustețea la răspunsuri lipsă se folosește modality dropout: în timpul antrenării, pentru fiecare exemplu "
            "chestionarul este ascuns în întregime cu probabilitate 0,3, iar fiecare câmp este ascuns separat cu probabilitate "
            "0,15. Un câmp ascuns primește trăsături 0 și masca 1, exact ca un răspuns lipsă real, deci modelul învață să se "
            "descurce și fără chestionar. Cum categoriile sunt dezechilibrate (de exemplu 44 de cazuri redness_rosacea față de "
            f"1.068 eczema_dermatitis), pierderea (loss, măsura erorii pe care o minimizează antrenarea) este entropia încrucișată "
            f"ponderată invers proporțional cu frecvența clasei. Optimizatorul este AdamW [{a}] cu rata de învățare 3·10⁻⁴ și "
            f"descreștere cosinusoidală [{c}], pe 15 epoci, cu precizie mixtă pe GPU. Se păstrează punctul de oprire (checkpoint) "
            f"cu cel mai bun macro-F1 pe setul de validare.",
        ]
        ev = [
            "Evaluarea se face o singură dată pe setul de testare, cu ponderile alese pe validare. Metricile sunt macro-F1 (media "
            "scorului F1 pe clase, care tratează egal clasele mici și mari) și acuratețea echilibrată (media recall-ului pe clase), "
            "raportate global și separat pe grupele eFST (I–II, III–IV, V–VI, lipsă), împreună cu diferența maximă dintre grupe. "
            "Pentru întrebarea privind răspunsurile lipsă, modelul este testat cu 0%, 25%, 50%, 75% și 100% dintre câmpurile "
            "chestionarului ascunse, și comparat cu modelul doar cu imagine. Fiecare configurație se rulează pentru cele cinci "
            "seed-uri (0–4), iar rezultatele se raportează ca medie și interval de variație. Scriptul este ml/train.py.",
        ]
        return model, ev
    model = [
        f"The model combines two branches by late fusion: the branches are processed separately and their information is "
        f"joined only before the final decision. The image branch is EfficientNet-B0 [{e}] from the timm library [{t_}] with "
        f"weights pretrained on ImageNet (transfer learning: the network starts from what it already learned on a large image "
        f"set and is retrained on SCIN). The questionnaire branch is a small network with one layer of 64 units that receives "
        f"the 40-feature vector together with the 6-value mask (46 numbers). The outputs of both branches are concatenated and "
        f"passed to a final layer that scores each of the four categories. A photo-only model, without the questionnaire "
        f"branch, is trained as a baseline.",
        "For robustness to missing answers we use modality dropout: during training, the whole questionnaire is hidden for a "
        "sample with probability 0.3, and each field is hidden independently with probability 0.15. A hidden field gets "
        "features 0 and mask 1, exactly like a real missing answer, so the model learns to work without the questionnaire. "
        "Because the categories are imbalanced (e.g. 44 redness_rosacea cases versus 1,068 eczema_dermatitis), the loss (the "
        "error measure that training minimises) is cross-entropy weighted inversely to class frequency. The optimiser is "
        f"AdamW [{a}] with learning rate 3e-4 and cosine decay [{c}], for 15 epochs, with mixed precision on GPU. The "
        f"checkpoint with the best validation macro-F1 is kept.",
    ]
    ev = [
        "Evaluation is done once on the test split with the weights chosen on validation. Metrics are macro-F1 (the mean of the "
        "per-class F1 scores, which treats small and large classes equally) and balanced accuracy (the mean per-class recall), "
        "reported overall and separately for each eFST group (I-II, III-IV, V-VI, missing), together with the maximum gap "
        "between groups. For the missing-answer question, the model is tested with 0%, 25%, 50%, 75% and 100% of the "
        "questionnaire fields hidden and compared with the photo-only model. Each configuration is run for the five seeds "
        "(0-4) and results are reported as mean and range. The script is ml/train.py.",
    ]
    return model, ev


t = DocEditor(str(ROOT / "docs" / "Teza_Licenta.docx"))
if t.heading("5.8 Modelul și fuziunea multimodală")._p.getnext().xpath("string(.)").strip().startswith("["):
    model, ev = build(t, "ro")
    t.replace_placeholder("5.8 Modelul și fuziunea multimodală", model)
    t.replace_placeholder("5.10 Protocolul de evaluare", ev)
    try:
        t.save()
        print("thesis updated")
    except PermissionError:
        print("THESIS LOCKED (open in Word) - not updated")

p = DocEditor(str(ROOT / "docs" / "Paper_Skin_Concern.docx"))
if p.heading("3.8 Model and training")._p.getnext().xpath("string(.)").strip().startswith("["):
    model, ev = build(p, "en")
    p.replace_placeholder("3.8 Model and training", model)
    p.replace_placeholder("3.9 Evaluation protocol", ev)
    try:
        p.save()
        print("paper updated")
    except PermissionError:
        print("PAPER LOCKED (open in Word) - not updated")
print("ok")
