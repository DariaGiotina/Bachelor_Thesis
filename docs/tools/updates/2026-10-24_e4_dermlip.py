"""E5 completed with DermLIP (rewrite thesis 8.10 / paper 4.10) and E4 calibration + abstention (new 8.11 / 4.11)."""
import sys
from pathlib import Path

from docx.oxml.ns import qn
from docx.shared import Inches
from docx.text.paragraph import Paragraph

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocEditor  # noqa: E402

REF = {
    "vit": ("https://arxiv.org/abs/2010.11929", "A. Dosovitskiy et al., An Image is Worth 16x16 Words: Transformers for "
            "Image Recognition at Scale, ICLR 2021"),
    "dino": ("https://arxiv.org/abs/2304.07193", "M. Oquab et al., DINOv2: Learning Robust Visual Features without "
             "Supervision, Transactions on Machine Learning Research, 2024"),
    "panderm": ("https://www.nature.com/articles/s41591-025-03747-y", "S. Yan et al., A multimodal vision foundation "
                "model for clinical dermatology, Nature Medicine, 2025"),
    "dermlip": ("https://arxiv.org/abs/2503.14911", "S. Yan et al., Derm1M: A Million-scale Vision-Language Dataset "
                "Aligned with Clinical Ontology Knowledge for Dermatology, ICCV 2025"),
    "clip": ("https://arxiv.org/abs/2103.00020", "A. Radford et al., Learning Transferable Visual Models From Natural "
             "Language Supervision, ICML 2021"),
    "guo": ("https://arxiv.org/abs/1706.04599", "C. Guo, G. Pleiss, Y. Sun, K. Q. Weinberger, On Calibration of Modern "
            "Neural Networks, ICML 2017"),
    "geifman": ("https://arxiv.org/abs/1705.08500", "Y. Geifman, R. El-Yaniv, Selective Classification for Deep Neural "
                "Networks, NeurIPS 2017"),
}
E4 = ROOT / "ml" / "results" / "e4"

# ------------------------------------------------------------------------------------------- E5
E5_ROWS = [
    ["EfficientNet-B0, fine-tuned (reference)", "0.519 ± 0.040", "0.610 ± 0.038", "0.079 ± 0.017", "reference"],
    ["EfficientNet-B0 ImageNet, frozen + linear probe", "0.447 ± 0.029", "0.543 ± 0.065", "0.139 ± 0.090",
     "-0.072 [-0.099, -0.044], 0/10"],
    ["ViT-B/16 ImageNet-21k, frozen + linear probe", "0.450 ± 0.043", "0.542 ± 0.069", "0.095 ± 0.028",
     "-0.069 [-0.097, -0.039], 0/10"],
    ["ViT-B/14 DINOv2, frozen + linear probe", "0.551 ± 0.064", "0.635 ± 0.059", "0.083 ± 0.027",
     "+0.032 [+0.005, +0.061], 7/10"],
    ["PanDerm-Base ViT-B/16, frozen + linear probe", "0.553 ± 0.049", "0.642 ± 0.071", "0.128 ± 0.071",
     "+0.034 [+0.003, +0.066], 8/10"],
    ["PanDerm-Large ViT-L/16, frozen + linear probe", "0.566 ± 0.044", "0.662 ± 0.065", "0.113 ± 0.062",
     "+0.047 [+0.017, +0.078], 7/10"],
    ["DermLIP ViT-B/16, frozen + linear probe", "0.603 ± 0.046", "0.689 ± 0.056", "0.161 ± 0.115",
     "+0.084 [+0.052, +0.114], 10/10"],
]
E5_RO_NAMES = ["EfficientNet-B0, ajustat fin (referință)", "EfficientNet-B0 ImageNet, înghețat + sondă liniară",
               "ViT-B/16 ImageNet-21k, înghețat + sondă liniară", "ViT-B/14 DINOv2, înghețat + sondă liniară",
               "PanDerm-Base ViT-B/16, înghețat + sondă liniară", "PanDerm-Large ViT-L/16, înghețat + sondă liniară",
               "DermLIP ViT-B/16, înghețat + sondă liniară"]

E5_RO = [
    "Experimentul E5 compară rețeaua EfficientNet-B0 ajustată fin (toate straturile antrenate pe SCIN, secțiunea 8.4) cu "
    "encodere înghețate urmate de o sondă liniară. Un encoder înghețat este o rețea pre-antrenată ale cărei ponderi nu se "
    "mai modifică: fiecare imagine este transformată o singură dată într-un vector de trăsături. Sonda liniară (linear "
    "probe) este un singur strat liniar antrenat peste aceste trăsături, cu aceeași pondere a claselor ca modelul de "
    "referință și cu o penalizare L2 (termen care micșorează ponderile pentru a evita supraînvățarea), aleasă pe "
    "validare. Sonda măsoară cât de utile sunt trăsăturile ca atare pentru categoriile noastre.",
    "S-au comparat șase encodere, în trei familii. (1) Supervizate pe ImageNet: EfficientNet-B0 (aceeași rețea, dar "
    "neajustată) și un Vision Transformer ViT-B/16 [{vit}] pre-antrenat pe ImageNet-21k (14 milioane de imagini, 21.000 "
    "de clase). Un Vision Transformer împarte imaginea în pătrate mici (patch-uri) și le prelucrează cu mecanismul de "
    "atenție, care cântărește cât contează fiecare patch pentru celelalte. (2) Auto-supervizat general: DINOv2 ViT-B/14 "
    "[{dino}], antrenat fără etichete pe 142 de milioane de imagini selectate, învățând ca două vederi diferite ale "
    "aceleiași imagini să aibă trăsături asemănătoare. (3) Modele fundație pentru dermatologie. Un model fundație este un "
    "model mare pre-antrenat pe date foarte multe și variate, gândit să fie refolosit pentru multe sarcini. PanDerm "
    "[{panderm}] este pre-antrenat auto-supervizat pe peste două milioane de imagini de boli de piele (clinice, "
    "dermatoscopice și din alte modalități), în două mărimi: Base (ViT-B/16, circa 86 de milioane de parametri) și Large "
    "(ViT-L/16, circa 303 milioane). DermLIP [{dermlip}] este un model imagine-text de tip CLIP [{clip}] (antrenare "
    "contrastivă: imaginea și descrierea ei sunt aduse aproape în același spațiu de trăsături, iar perechile "
    "nepotrivite sunt îndepărtate), antrenat pe circa un milion de perechi imagine-text din dermatologie; se folosește "
    "doar encoderul de imagine (ViT-B/16). Ponderile PanDerm au fost încărcate în implementarea timm a ViT; conversia a "
    "fost verificată față de codul autorilor (diferență maximă a trăsăturilor 2·10⁻⁶, adică doar rotunjire numerică).",
    "Rezultatele sunt în Tabelul 8.9. Sondele pe trăsături ImageNet rămân mult sub modelul ajustat fin (-0,072 și -0,069 "
    "macro-F1, mai slabe în toate cele zece seed-uri): pentru rețelele antrenate pe etichete ImageNet, ajustarea fină pe "
    "piele este necesară. Celelalte patru encodere depășesc modelul ajustat fin, iar ordinea urmează cât de apropiate de "
    "dermatologie sunt datele de pre-antrenare: DINOv2 +0,032 [+0,005; +0,061] (7/10 seed-uri, t-test pereche "
    "p = 0,185), PanDerm-Base +0,034 (8/10, p = 0,069), PanDerm-Large +0,047 [+0,017; +0,078] (7/10, p = 0,022) și "
    "DermLIP +0,084 [+0,052; +0,114], mai bun în toate cele zece seed-uri (p < 0,001; Wilcoxon p = 0,002). DermLIP "
    "atinge macro-F1 0,603 și acuratețe echilibrată 0,689. Câștigurile sunt pozitive la toate tonurile de piele; pentru "
    "DermLIP ele rămân semnificative după corecția Holm pentru eFST I-II, eMST 1-3 și eMST 4-6, precum și pentru acne "
    "(+0,163), eczema_dermatitis (+0,066) și normal_other (+0,156). Pentru redness_rosacea toate sondele sunt mai slabe "
    "sau la același nivel (DermLIP -0,050, interval care include 0; PanDerm-Large -0,119), însă categoria are în medie "
    "doar 6 cazuri de test pe seed.",
    "Două limite contează pentru aplicație. Prima este calibrarea: eroarea de calibrare ECE (diferența medie dintre "
    "încrederea afișată și acuratețea reală) este mai mare pentru sondele PanDerm și DermLIP (0,113-0,161) decât pentru "
    "modelul ajustat fin (0,079); corecția ei este tratată în secțiunea 8.11. A doua este licența: PanDerm și DermLIP "
    "sunt publicate sub CC BY-NC-ND 4.0, care permite doar cercetare necomercială și interzice distribuirea unor versiuni "
    "modificate, în timp ce DINOv2 are licența Apache 2.0, care permite și utilizarea comercială.",
]
E5_EN = [
    "Experiment E5 compares the fine-tuned EfficientNet-B0 (all layers trained on SCIN, Section 4.4) with frozen "
    "encoders followed by a linear probe. A frozen encoder is a pre-trained network whose weights are no longer changed: "
    "each image is turned once into a feature vector. The linear probe is a single linear layer trained on these "
    "features, with the same class weighting as the reference model and an L2 penalty (a term that shrinks the weights "
    "to avoid overfitting) chosen on validation. The probe measures how useful the features are for our categories as "
    "they are.",
    "Six encoders from three families were compared. (1) Supervised on ImageNet: EfficientNet-B0 (the same network, but "
    "not fine-tuned) and a Vision Transformer ViT-B/16 [{vit}] pre-trained on ImageNet-21k (14 million images, 21,000 "
    "classes). A Vision Transformer splits the image into small squares (patches) and processes them with attention, "
    "which weighs how much each patch matters to the others. (2) General self-supervised: DINOv2 ViT-B/14 [{dino}], "
    "trained without labels on 142 million curated images by learning to give two different views of the same image "
    "similar features. (3) Dermatology foundation models. A foundation model is a large model pre-trained on very much "
    "and very varied data, meant to be reused for many tasks. PanDerm [{panderm}] is pre-trained self-supervised on over "
    "two million skin-disease images (clinical, dermoscopic and other modalities), in two sizes: Base (ViT-B/16, about "
    "86 million parameters) and Large (ViT-L/16, about 303 million). DermLIP [{dermlip}] is a CLIP-style image-text "
    "model [{clip}] (contrastive training: an image and its description are pulled together in one feature space and "
    "mismatched pairs are pushed apart), trained on about one million dermatology image-text pairs; only its image "
    "encoder (ViT-B/16) is used. The PanDerm weights were loaded into the timm ViT implementation; the conversion was "
    "checked against the authors' code (maximum feature difference 2e-6, i.e. numerical rounding only).",
    "Table 10 gives the results. The probes on ImageNet features stay well below the fine-tuned model (-0.072 and "
    "-0.069 macro-F1, worse in all ten seeds): for networks trained on ImageNet labels, fine-tuning on skin is needed. "
    "The other four encoders exceed the fine-tuned model, in the order of how close their pre-training data are to "
    "dermatology: DINOv2 +0.032 [+0.005, +0.061] (7/10 seeds, paired t-test p = 0.185), PanDerm-Base +0.034 (8/10, "
    "p = 0.069), PanDerm-Large +0.047 [+0.017, +0.078] (7/10, p = 0.022) and DermLIP +0.084 [+0.052, +0.114], better in "
    "all ten seeds (p < 0.001; Wilcoxon p = 0.002). DermLIP reaches macro-F1 0.603 and balanced accuracy 0.689. The gains "
    "are positive for every skin tone; for DermLIP they survive the Holm correction for eFST I-II, eMST 1-3 and eMST "
    "4-6, and for acne (+0.163), eczema_dermatitis (+0.066) and normal_other (+0.156). For redness_rosacea every probe "
    "is weaker or level (DermLIP -0.050, interval including 0; PanDerm-Large -0.119), but this category has only 6 test "
    "cases per seed on average.",
    "Two limits matter for the app. The first is calibration: the expected calibration error ECE (the mean gap between "
    "the confidence shown and the actual accuracy) is higher for the PanDerm and DermLIP probes (0.113-0.161) than for "
    "the fine-tuned model (0.079); correcting it is the subject of Section 4.11. The second is the licence: PanDerm and "
    "DermLIP are released under CC BY-NC-ND 4.0, which allows only non-commercial research and forbids distributing "
    "modified versions, whereas DINOv2 is Apache 2.0, which also allows commercial use.",
]

# ------------------------------------------------------------------------------------------- E4
E4_ROWS = [  # model, T, ECE before -> after, AURC, accuracy, selective accuracy at 80% coverage
    ["EfficientNet-B0, fine-tuned", "0.93", "0.079 → 0.074", "0.345", "0.564", "0.607"],
    ["FiLM fusion (photo + questionnaire)", "1.01", "0.076 → 0.079", "0.322", "0.584", "0.616"],
    ["DINOv2 + linear probe", "1.06", "0.083 → 0.061", "0.256", "0.626", "0.676"],
    ["PanDerm-Large + linear probe", "1.44", "0.113 → 0.067", "0.226", "0.641", "0.699"],
    ["DermLIP + linear probe", "1.15", "0.161 → 0.077", "0.229", "0.670", "0.720"],
]
E4_RO_NAMES = ["EfficientNet-B0, ajustat fin", "Fuziune FiLM (fotografie + chestionar)", "DINOv2 + sondă liniară",
               "PanDerm-Large + sondă liniară", "DermLIP + sondă liniară"]
TONE_ROWS = [  # model, abstention eFST I-II / III-IV / V-VI, V-VI - I-II, selective accuracy eMST 4-6 - 1-3
    ["EfficientNet-B0, fine-tuned", "22.0", "21.5", "21.2", "-0.8 [-7.1, +5.3]", "-8.9 [-13.9, -4.1]"],
    ["FiLM fusion", "20.2", "20.4", "14.2", "-6.0 [-10.8, -0.5]", "-8.1 [-12.6, -3.3]"],
    ["DINOv2 + probe", "22.5", "19.2", "19.0", "-3.5 [-9.0, +1.8]", "-4.9 [-9.3, -0.4]"],
    ["PanDerm-Large + probe", "21.2", "20.1", "25.2", "+4.0 [-1.7, +10.1]", "-4.6 [-9.2, -0.2]"],
    ["DermLIP + probe", "20.3", "21.0", "24.8", "+4.5 [-1.7, +10.2]", "-6.4 [-10.8, -1.7]"],
]
TONE_RO_NAMES = ["EfficientNet-B0, ajustat fin", "Fuziune FiLM", "DINOv2 + sondă", "PanDerm-Large + sondă",
                 "DermLIP + sondă"]

E4_RO = [
    "Experimentul E4 răspunde la RQ4: când modelul spune „nu sunt sigur, consultați un specialist”, face acest lucru la "
    "fel de des și la fel de corect pentru toate tonurile de piele? Sunt comparate cinci modele pe aceleași cazuri de "
    "test SCIN și aceleași zece seed-uri: EfficientNet-B0 ajustat fin, fuziunea FiLM (cea mai bună fuziune din E1) și "
    "sondele DINOv2, PanDerm-Large și DermLIP din E5 (`ml/run_e4.py`, `ml/calibrate.py`, `ml/abstain.py`).",
    "Calibrarea. Un model este bine calibrat dacă, dintre cazurile la care afișează o încredere de 70%, circa 70% sunt "
    "corecte. Scalarea temperaturii [{guo}] împarte ieșirile brute ale modelului (logiții) la un singur număr T înainte "
    "de softmax: T > 1 coboară încrederile prea mari, T < 1 le ridică pe cele prea mici, iar clasa prezisă nu se schimbă. "
    "T este ales pe validare, pentru fiecare seed, minimizând log-verosimilitatea negativă (NLL, media lui -log din "
    "probabilitatea dată clasei corecte; mai mică este mai bine). Pentru modelele care au salvat doar probabilitățile, "
    "logiții se obțin ca logaritmul probabilităților (softmax-ul nu se schimbă dacă se adună aceeași constantă la toți "
    "logiții); pentru EfficientNet-B0 și FiLM, probabilitățile complete au fost recalculate din checkpoint-uri, iar "
    "predicțiile au coincis 100% cu cele salvate.",
    "Abținerea. Regula este: modelul răspunde doar dacă încrederea calibrată este cel puțin τ; altfel afișează "
    "recomandarea de a consulta un specialist. τ se alege pe validare astfel încât 80% din cazuri să primească răspuns "
    "(acoperire, coverage, de 80%) și se aplică neschimbat pe test. Fixarea acoperirii, nu a lui τ, face modelele "
    "comparabile: toate se pot abține pe aceeași proporție de cazuri, iar întrebarea este doar dacă se abțin pe cazurile "
    "potrivite și la fel de des pentru fiecare ton de piele. Se raportează: rata de abținere, acuratețea selectivă "
    "(acuratețea pe cazurile la care modelul răspunde), precizia abținerii (proporția cazurilor refuzate care ar fi fost "
    "greșite) și curba risc-acoperire [{geifman}] (rata de eroare pe cazurile cu răspuns, când se păstrează doar cele "
    "mai sigure x% dintre cazuri) cu aria de sub ea, AURC (mai mică este mai bine; T nu o schimbă, deoarece păstrează "
    "ordinea încrederilor). Intervalele pe grupe provin dintr-un bootstrap pe cazuri în interiorul fiecărui seed; "
    "diferențele dintre grupe sunt pereche și nu sunt corectate pentru comparații multiple.",
    "Rezultate generale (Tabelul 8.10, Figura 8.2). Scalarea temperaturii aduce toate modelele la o eroare de calibrare "
    "apropiată (ECE 0,061-0,079): pentru sondele PanDerm-Large și DermLIP eroarea scade aproape la jumătate (0,113 → "
    "0,067 și 0,161 → 0,077), iar pentru EfficientNet-B0, deja calibrat, T este aproape 1. Sondele separă mult mai bine "
    "răspunsurile corecte de cele greșite prin încredere: AURC scade față de EfficientNet-B0 cu 0,089 (DINOv2), 0,119 "
    "(PanDerm-Large) și 0,116 (DermLIP), în toate cele zece seed-uri; fuziunea FiLM aduce un câștig mic (-0,023, 8/10). "
    "La 80% acoperire, acuratețea selectivă este 0,607 pentru EfficientNet-B0 și 0,720 pentru DermLIP.",
    "Rezultate pe tonuri de piele (Tabelul 8.11, Figura 8.3). Pe SCIN, rata de abținere este aproape aceeași pentru "
    "toate grupele eFST și eMST (20-25%); singura diferență cu interval care exclude 0 este că fuziunea FiLM se abține "
    "mai rar pe eFST V-VI (-6,0 puncte procentuale). Corectitudinea răspunsurilor nu este însă egală: pe cazurile eMST "
    "4-6, acuratețea selectivă este mai mică decât pe eMST 1-3 la toate modelele (de la -4,6 la -8,9 puncte, toate "
    "intervalele sub 0). Regula de abținere nu elimină deci decalajul, deoarece modelul nu este mai nesigur acolo unde "
    "greșește mai des. Sondele pe modele fundație reduc decalajul (de la -8,9 la -4,6 până la -6,4 puncte), dar nu îl "
    "elimină. Pe Fitzpatrick17k (zero-shot, cu T și τ din SCIN, intervale prin bootstrap pe imagini), EfficientNet-B0 "
    "se abține mai des pe pielea închisă (27,5% la eFST I-II, 38,8% la V-VI; +11,2 [8,0; 14,1] puncte) și, când "
    "răspunde, are o acuratețe mai mică (-5,0 [-9,5; -0,4] puncte). Pe fotografii dintr-un domeniu necunoscut, "
    "recomandarea de a consulta un specialist ar apărea deci mai des pentru persoanele cu piele închisă.",
    "Răspunsul la RQ4: în domeniul de antrenare, modelele sunt nesigure la fel de des pentru toate tonurile, dar nu la "
    "fel de corect: pentru eMST 4-6 răspunsurile date sunt mai des greșite. În afara domeniului, abținerea crește odată "
    "cu tonul pielii. Pentru aplicație rezultă trei decizii: încrederea afișată este cea calibrată; pragul τ se alege "
    "pentru acoperirea dorită și se verifică pe tonuri; modelul candidat este o sondă pe un model fundație. DermLIP și "
    "PanDerm au cele mai bune rezultate, dar licența lor permite doar cercetare necomercială; DINOv2 (Apache 2.0) "
    "rămâne cu 0,069 acuratețe selectivă peste EfficientNet-B0 și are cea mai mică eroare de calibrare după scalare "
    "(0,061), deci este varianta potrivită pentru o aplicație care poate fi distribuită.",
]
E4_EN = [
    "Experiment E4 answers RQ4: when the model says \"not sure, please see a professional\", does it do so equally often "
    "and equally correctly for every skin tone? Five models are compared on the same SCIN test cases and the same ten "
    "seeds: the fine-tuned EfficientNet-B0, FiLM fusion (the best fusion arm in E1) and the DINOv2, PanDerm-Large and "
    "DermLIP probes from E5 (`ml/run_e4.py`, `ml/calibrate.py`, `ml/abstain.py`).",
    "Calibration. A model is well calibrated if, among the cases where it shows 70% confidence, about 70% are correct. "
    "Temperature scaling [{guo}] divides the model's raw outputs (logits) by one number T before the softmax: T > 1 "
    "lowers confidences that are too high, T < 1 raises those that are too low, and the predicted class does not change. "
    "T is chosen on validation, per seed, by minimising the negative log-likelihood (NLL, the mean of -log of the "
    "probability given to the true class; lower is better). For models that stored only probabilities, logits are "
    "taken as log-probabilities (the softmax does not change when the same constant is added to every logit); for "
    "EfficientNet-B0 and FiLM the full probabilities were recomputed from the checkpoints, and the predictions matched "
    "the stored ones 100%.",
    "Abstention. The rule is: the model answers only if its calibrated confidence is at least tau; otherwise it shows "
    "the advice to see a professional. tau is chosen on validation so that 80% of cases get an answer (80% coverage) and "
    "is applied unchanged on test. Fixing the coverage rather than tau makes the models comparable: each may abstain on "
    "the same share of cases, so the question is only whether it abstains on the right cases, and equally often for "
    "every skin tone. Reported are the abstention rate, the selective accuracy (accuracy on the cases the model "
    "answers), the abstention precision (share of declined cases that would have been wrong) and the risk-coverage "
    "curve [{geifman}] (error rate on the answered cases when only the most confident x% are kept) with the area under "
    "it, AURC (lower is better; T does not change it because it keeps the order of the confidences). Group intervals "
    "come from a case bootstrap within each seed; group differences are paired and not corrected for multiple "
    "comparisons.",
    "Overall results (Table 11, Figure 2). Temperature scaling brings every model to a similar calibration error (ECE "
    "0.061-0.079): for the PanDerm-Large and DermLIP probes the error almost halves (0.113 → 0.067 and 0.161 → 0.077), "
    "while for the already calibrated EfficientNet-B0 T is close to 1. The probes separate right from wrong answers by "
    "confidence much better: AURC drops against EfficientNet-B0 by 0.089 (DINOv2), 0.119 (PanDerm-Large) and 0.116 "
    "(DermLIP), in all ten seeds; FiLM fusion gives a small gain (-0.023, 8/10). At 80% coverage the selective accuracy "
    "is 0.607 for EfficientNet-B0 and 0.720 for DermLIP.",
    "Results by skin tone (Table 12, Figure 3). On SCIN the abstention rate is almost the same for every eFST and eMST "
    "group (20-25%); the only difference whose interval excludes 0 is that FiLM fusion abstains less often on eFST V-VI "
    "(-6.0 percentage points). Correctness, however, is not equal: on eMST 4-6 cases the selective accuracy is lower "
    "than on eMST 1-3 for every model (-4.6 to -8.9 points, all intervals below 0). The abstention rule therefore does "
    "not remove the gap, because the model is not more uncertain where it is more often wrong. The foundation-model "
    "probes narrow the gap (from -8.9 to between -4.6 and -6.4 points) but do not close it. On Fitzpatrick17k "
    "(zero-shot, with the SCIN T and tau, intervals from an image-level bootstrap) EfficientNet-B0 abstains more often "
    "on dark skin (27.5% for eFST I-II, 38.8% for V-VI; +11.2 [8.0, 14.1] points) and, when it answers, is less "
    "accurate (-5.0 [-9.5, -0.4] points). On photos from an unfamiliar domain, the advice to see a professional would "
    "thus appear more often for people with dark skin.",
    "Answer to RQ4: in the training domain the models are uncertain equally often for every tone, but not equally "
    "correctly: for eMST 4-6 the answers they do give are more often wrong. Outside the domain, abstention grows with "
    "skin tone. Three decisions follow for the app: the confidence shown is the calibrated one; tau is set for the "
    "desired coverage and checked per tone; the candidate model is a probe on a foundation model. DermLIP and PanDerm "
    "score best, but their licence allows only non-commercial research; DINOv2 (Apache 2.0) still beats EfficientNet-B0 "
    "by 0.069 selective accuracy and has the lowest calibration error after scaling (0.061), so it is the option for an "
    "app that can be distributed.",
]


def ro(s: str) -> str:
    return s.replace(", ", "; ").replace(".", ",").replace("reference", "referință")


def clear_section(ed, head_text):
    h = ed.heading(head_text)
    nxt = h._p.getnext()
    while nxt is not None:
        if nxt.tag == qn("w:p") and Paragraph(nxt, h._parent).style.name.startswith("Heading"):
            return Paragraph(nxt, h._parent)
        gone, nxt = nxt, nxt.getnext()
        gone.getparent().remove(gone)
    raise ValueError(f"no heading after {head_text!r}")


def add_table(ed, anchor, rows, caption):
    ed.body_paragraph_before(anchor, caption)
    tbl = ed.doc.add_table(rows=len(rows), cols=len(rows[0]))
    try:
        tbl.style = ed.doc.styles["Table Grid"]
    except KeyError:
        pass
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            tbl.cell(i, j).text = v
            if i == 0:
                for r in tbl.cell(i, j).paragraphs[0].runs:
                    r.bold = True
    anchor._p.addprevious(tbl._tbl)


def add_figure(ed, anchor, path, caption, width=5.8):
    p = ed.body_paragraph_before(anchor, "")
    p.add_run().add_picture(str(path), width=Inches(width))
    ed.body_paragraph_before(anchor, caption)


DOCS = {
    "Teza_Licenta.docx": dict(
        e5_head="8.10 Encodere pre-antrenate înghețate și sondă liniară (E5)", e5=E5_RO,
        e5_table=[["Model", "Macro-F1", "Acuratețe echilibrată", "ECE", "Diferență față de modelul ajustat fin"]]
        + [[n] + [ro(x) for x in r[1:]] for n, r in zip(E5_RO_NAMES, E5_ROWS)],
        e5_cap="Tabelul 8.9. Experimentul E5 pe testul SCIN (zece seed-uri; medie ± abatere standard; diferență pereche "
               "de macro-F1 cu interval bootstrap de 95% și numărul de seed-uri mai bune).",
        e4_head="8.11 Calibrarea încrederii și abținerea pe tonuri de piele (E4)", e4=E4_RO,
        next_head="Capitolul 9. Concluzii și direcții viitoare",
        t1=[["Model", "T", "ECE înainte → după", "AURC", "Acuratețe", "Acuratețe selectivă (80%)"]]
        + [[n] + [ro(x) for x in r[1:]] for n, r in zip(E4_RO_NAMES, E4_ROWS)],
        t1_cap="Tabelul 8.10. Calibrare și predicție selectivă pe testul SCIN (medii pe zece seed-uri; acoperire țintă "
               "80%, τ ales pe validare).",
        t2=[["Model", "Abținere eFST I-II (%)", "III-IV (%)", "V-VI (%)", "V-VI minus I-II", "Acuratețe selectivă eMST "
             "4-6 minus 1-3"]] + [[n] + [ro(x) for x in r[1:]] for n, r in zip(TONE_RO_NAMES, TONE_ROWS)],
        t2_cap="Tabelul 8.11. Abținerea pe tonuri de piele (SCIN, cazuri de test din zece seed-uri; diferențe în puncte "
               "procentuale cu interval bootstrap de 95%).",
        f1_cap="Figura 8.2. Curba risc-acoperire pe testul SCIN (medie pe zece seed-uri): rata de eroare pe cazurile cu "
               "răspuns când se păstrează doar cele mai sigure x% dintre cazuri.",
        f2_cap="Figura 8.3. Rata de abținere pe grupe eFST și eMST la 80% acoperire (interval bootstrap de 95%)."),
    "Paper_Skin_Concern.docx": dict(
        e5_head="4.10 Frozen pre-trained encoders and linear probe (E5)", e5=E5_EN,
        e5_table=[["Model", "Macro-F1", "Balanced accuracy", "ECE", "Difference vs fine-tuned model"]] + E5_ROWS,
        e5_cap="Table 10. Experiment E5 on the SCIN test split (ten seeds; mean ± standard deviation; paired macro-F1 "
               "difference with 95% bootstrap interval and number of seeds better).",
        e4_head="4.11 Calibration and abstention by skin tone (E4)", e4=E4_EN, next_head="5. Discussion",
        t1=[["Model", "T", "ECE before → after", "AURC", "Accuracy", "Selective accuracy (80%)"]] + E4_ROWS,
        t1_cap="Table 11. Calibration and selective prediction on the SCIN test split (means over ten seeds; target "
               "coverage 80%, tau chosen on validation).",
        t2=[["Model", "Abstention eFST I-II (%)", "III-IV (%)", "V-VI (%)", "V-VI minus I-II",
             "Selective accuracy eMST 4-6 minus 1-3"]] + TONE_ROWS,
        t2_cap="Table 12. Abstention by skin tone (SCIN test cases of ten seeds; differences in percentage points with "
               "95% bootstrap interval).",
        f1_cap="Figure 2. Risk-coverage curve on the SCIN test split (mean over ten seeds): error rate on the answered "
               "cases when only the most confident x% are kept.",
        f2_cap="Figure 3. Abstention rate by eFST and eMST group at 80% coverage (95% bootstrap interval)."),
}

for path, d in DOCS.items():
    ed = DocEditor(str(ROOT / "docs" / path))
    if ed.has_heading(d["e4_head"]):
        print(path, "already updated")
        continue
    n = {k: ed.add_reference(v[1], v[0]) for k, v in REF.items()}
    anchor = clear_section(ed, d["e5_head"])
    for t in d["e5"][:2]:
        ed.body_paragraph_before(anchor, t.format(**n))
    add_table(ed, anchor, d["e5_table"], d["e5_cap"])
    for t in d["e5"][2:]:
        ed.body_paragraph_before(anchor, t.format(**n))
    anchor = ed.heading(d["next_head"])
    ed.heading_before(anchor, d["e4_head"], 2)
    for t in d["e4"][:3]:
        ed.body_paragraph_before(anchor, t.format(**n))
    ed.body_paragraph_before(anchor, d["e4"][3].format(**n))
    add_table(ed, anchor, d["t1"], d["t1_cap"])
    add_figure(ed, anchor, E4 / "e4_risk_coverage.png", d["f1_cap"])
    ed.body_paragraph_before(anchor, d["e4"][4].format(**n))
    add_table(ed, anchor, d["t2"], d["t2_cap"])
    add_figure(ed, anchor, E4 / "e4_abstention_by_tone.png", d["f2_cap"], width=6.3)
    ed.body_paragraph_before(anchor, d["e4"][5].format(**n))
    try:
        ed.save()
        print(path, "updated")
    except PermissionError:
        print(path, "LOCKED (open in Word) - not updated")
