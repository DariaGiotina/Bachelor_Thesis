"""Task 3.4: answer dropout with a sampled rate. Method in thesis 5.8 / paper 3.8, results (E2) in thesis 8.6 / paper 4.6."""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocEditor  # noqa: E402

NEVEROVA = ("https://doi.org/10.1109/TPAMI.2015.2461544",
            "N. Neverova, C. Wolf, G. Taylor, F. Nebout, ModDrop: Adaptive Multi-Modal Gesture Recognition, "
            "IEEE Transactions on Pattern Analysis and Machine Intelligence 38(8), 2016")
SRIVASTAVA = ("https://jmlr.org/papers/v15/srivastava14a.html",
              "N. Srivastava, G. Hinton, A. Krizhevsky, I. Sutskever, R. Salakhutdinov, Dropout: A Simple Way to "
              "Prevent Neural Networks from Overfitting, Journal of Machine Learning Research 15, 2014")

METHOD_RO = [
    "Pe lângă regimul fix de mai sus, a fost implementat un al doilea regim de ascundere a răspunsurilor la "
    "antrenare, numit în continuare „dropout pe răspunsuri cu rată eșantionată” (fișierul `ml/dropout_utils.py`, "
    "funcția `apply_answer_dropout`, opțiunea `--q_dropout random` din `ml/train.py` și `ml/run_fusion.py`). "
    "Termenul de dropout desemnează, în general, eliminarea aleatoare a unor unități ale rețelei la antrenare, ca "
    "rețeaua să nu depindă de niciuna în parte [{sriv}]; dropout-ul pe modalitate aplică aceeași idee unei întregi "
    "surse de date (aici, chestionarul) [{nev}]. În noul regim, pentru fiecare lot (batch, grupul de 32 de cazuri "
    "procesat într-un pas de antrenare) se extrage o rată p dintr-o distribuție uniformă între 0 și 1 (orice valoare "
    "din interval este la fel de probabilă), iar fiecare întrebare a fiecărui caz este ascunsă cu probabilitatea p; "
    "independent, întregul chestionar al unui caz este ascuns cu probabilitatea 0,1. Câmpurile ascunse primesc "
    "trăsături 0 și bitul de mască 1, exact ca un răspuns lipsă real, deci modelul nu poate distinge o întrebare "
    "ascunsă de una la care utilizatorul nu a răspuns. Spre deosebire de regimul fix (30% chestionar întreg, 15% pe "
    "întrebare), rata eșantionată pe lot expune modelul la toate nivelurile de completare, de la chestionare complete "
    "la chestionare goale. Ponderile se salvează în fișierele `fusion_dropout_<variantă>_seed<k>.pt`. Trei regimuri "
    "sunt comparate în experimentul E2: fără ascundere (none), regimul fix (fixed) și rata eșantionată (random).",
]
METHOD_EN = [
    "Besides the fixed regime above, a second regime for hiding answers during training was implemented, called here "
    "answer dropout with a sampled rate (`ml/dropout_utils.py`, function `apply_answer_dropout`, option "
    "`--q_dropout random` in `ml/train.py` and `ml/run_fusion.py`). Dropout in general means randomly removing units of "
    "a network during training so that it does not depend on any single one [{sriv}]; modality dropout applies the same "
    "idea to a whole input source (here, the questionnaire) [{nev}]. In the new regime, for every batch (the group of 32 "
    "cases processed in one training step) a rate p is drawn from a uniform distribution between 0 and 1 (every value in "
    "the interval is equally likely), and each question of each case is hidden with probability p; independently, the "
    "whole questionnaire of a case is hidden with probability 0.1. Hidden fields get features 0 and mask bit 1, exactly "
    "like a real missing answer, so the model cannot tell a hidden question from one the user skipped. Unlike the fixed "
    "regime (30% whole questionnaire, 15% per question), sampling the rate per batch exposes the model to every level "
    "of completeness, from full to empty questionnaires. Weights are saved as `fusion_dropout_<variant>_seed<k>.pt`. "
    "Experiment E2 compares three regimes: no hiding (none), the fixed regime (fixed) and the sampled rate (random).",
]

RES_RO = [
    "Experimentul E2 răspunde la întrebarea de cercetare RQ2: cât pierde modelul de fuziune când lipsesc răspunsuri "
    "și dacă antrenarea cu răspunsuri ascunse îl face mai robust (robustețe înseamnă aici că performanța scade puțin "
    "când datele de intrare sunt incomplete). Modelul de fuziune prin concatenare (EfficientNet-B0, pierdere ponderată) "
    "a fost antrenat în cele trei regimuri de la secțiunea 5.8 pe aceleași zece seed-uri, iar fiecare model a fost "
    "testat cu o proporție r de întrebări ascunse (r = 0; 0,25; 0,5; 0,75; 1, pe lângă răspunsurile care lipsesc "
    "natural), cu aceleași întrebări ascunse pentru toate modelele (`ml/run_e2_dropout.py`; rezultatele în "
    "`ml/results/e2/`). Tabelul 8.6 arată macro-F1 pe test.",
    "Cele trei regimuri dau rezultate practic identice. Diferența dintre rata eșantionată și antrenarea fără ascundere "
    "este între +0,001 și +0,009 la toate valorile lui r, cu intervale de încredere de 95% care conțin zero (de "
    "exemplu +0,003 [-0,015; +0,020] la r = 1); la fel între regimul fix și cel fără ascundere (+0,000 până la "
    "+0,009) și între rata eșantionată și regimul fix (-0,004 până la +0,002). Nici un regim nu depășește modelul doar "
    "cu imagine (diferențe între -0,005 și -0,020, nesemnificative după corecție, cu excepția unei valori izolate "
    "p = 0,049 fără corecție pentru regimul fără ascundere la r = 0,75).",
    "Rezultatul principal este că pierderea la ascunderea tuturor răspunsurilor este foarte mică chiar și pentru "
    "modelul antrenat fără ascundere: -0,001 [-0,016; +0,015], față de -0,010 pentru regimul fix și -0,003 "
    "[-0,009; +0,003] pentru rata eșantionată (cel mai îngust interval). Altfel spus, modelul de fuziune se bazează "
    "aproape în întregime pe fotografie, deci nu are ce pierde când chestionarul lipsește. Acest lucru este în acord "
    "cu secțiunea 8.5 (semnal slab al chestionarului): dropout-ul pe răspunsuri nu poate proteja o informație pe care "
    "modelul nu o folosește. Pe grupe de ton al pielii (eFST, eMST) nicio diferență față de regimul fără ascundere nu "
    "este semnificativă după corecția Holm; grupele mici (eFST V–VI, circa 23 de cazuri pe seed; eMST 7–10, 11 cazuri) "
    "variază mult între seed-uri și nu permit concluzii. Pentru aplicație, consecința practică este că modelul "
    "antrenat cu rată eșantionată poate fi folosit fără risc atunci când utilizatorul sare peste întrebări, dar "
    "răspunsul la RQ2 trebuie formulat cu prudență: robustețea observată provine din faptul că chestionarul contribuie "
    "puțin, nu din antrenarea cu răspunsuri ascunse.",
]
RES_EN = [
    "Experiment E2 addresses research question RQ2: how much the fusion model loses when answers are missing, and "
    "whether training with hidden answers makes it more robust (robustness here means that performance drops little "
    "when inputs are incomplete). The concatenation fusion model (EfficientNet-B0, weighted loss) was trained under the "
    "three regimes of Section 3.8 on the same ten seeds, and each model was tested with a share r of questions hidden "
    "(r = 0, 0.25, 0.5, 0.75, 1, on top of the naturally missing answers), with the same hidden questions for every "
    "model (`ml/run_e2_dropout.py`; results in `ml/results/e2/`). Table 5 shows test macro-F1.",
    "The three regimes give practically identical results. The difference between the sampled rate and training "
    "without hiding is between +0.001 and +0.009 at every r, with 95% confidence intervals that include zero (e.g. "
    "+0.003 [-0.015, +0.020] at r = 1); likewise between the fixed regime and no hiding (+0.000 to +0.009) and between "
    "the sampled rate and the fixed regime (-0.004 to +0.002). No regime exceeds the photo-only model (differences from "
    "-0.005 to -0.020, not significant after correction, except one isolated uncorrected p = 0.049 for no hiding at "
    "r = 0.75).",
    "The main finding is that the loss when every answer is hidden is very small even for the model trained without "
    "hiding: -0.001 [-0.016, +0.015], versus -0.010 for the fixed regime and -0.003 [-0.009, +0.003] for the sampled "
    "rate (the narrowest interval). In other words, the fusion model relies almost entirely on the photo, so it has "
    "little to lose when the questionnaire is missing. This agrees with Section 4.5 (weak questionnaire signal): answer "
    "dropout cannot protect information the model does not use. By skin-tone group (eFST, eMST), no difference against "
    "the no-hiding regime is significant after Holm correction; small groups (eFST V-VI, about 23 cases per seed; "
    "eMST 7-10, 11 cases) vary strongly between seeds and allow no conclusion. For the app, the practical consequence "
    "is that the model trained with a sampled rate can be used safely when users skip questions, but the answer to RQ2 "
    "must be worded carefully: the observed robustness comes from the questionnaire contributing little, not from "
    "training with hidden answers.",
]

HEAD = ["Regim / Regime", "r = 0", "r = 0.25", "r = 0.5", "r = 0.75", "r = 1", "r=1 - r=0"]
DATA = [
    ["image_only", "0.519 ± 0.040", "0.519", "0.519", "0.519", "0.519", "—"],
    ["none", "0.505 ± 0.036", "0.506", "0.506", "0.499", "0.504 ± 0.035", "-0.001 [-0.016, +0.015]"],
    ["fixed", "0.514 ± 0.040", "0.508", "0.511", "0.508", "0.505 ± 0.042", "-0.010 [-0.022, +0.003]"],
    ["random", "0.510 ± 0.037", "0.509", "0.508", "0.508", "0.507 ± 0.039", "-0.003 [-0.009, +0.003]"],
]


def ro(s: str) -> str:
    return s.replace(", ", "; ").replace(".", ",")


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


for path, method_head, method, head, next_head, res, rows, cap in (
        ("Teza_Licenta.docx", "5.8 Modelul și fuziunea multimodală", METHOD_RO,
         "8.6 Antrenarea cu răspunsuri ascunse (E2)", "Capitolul 9. Concluzii și direcții viitoare", RES_RO,
         [["Regim", "r = 0", "r = 0,25", "r = 0,5", "r = 0,75", "r = 1", "r = 1 minus r = 0"]]
         + [[d[0]] + [ro(x) for x in d[1:]] for d in DATA],
         "Tabelul 8.6. Macro-F1 pe test în funcție de proporția r de întrebări ascunse, pe zece seed-uri (fuziune prin "
         "concatenare, EfficientNet-B0; medie ± abatere standard; ultima coloană: diferența pereche cu interval "
         "bootstrap de 95%)."),
        ("Paper_Skin_Concern.docx", "3.8 Model and training", METHOD_EN,
         "4.6 Training with hidden answers (E2)", "5. Discussion", RES_EN,
         [["Regime", "r = 0", "r = 0.25", "r = 0.5", "r = 0.75", "r = 1", "r = 1 minus r = 0"]] + DATA,
         "Table 5. Test macro-F1 by the share r of hidden questions over ten seeds (concatenation fusion, "
         "EfficientNet-B0; mean ± standard deviation; last column: paired difference with 95% bootstrap interval).")):
    ed = DocEditor(str(ROOT / "docs" / path))
    if ed.has_heading(head):
        print(path, "already updated")
        continue
    n = {"sriv": ed.add_reference(SRIVASTAVA[1], SRIVASTAVA[0]), "nev": ed.add_reference(NEVEROVA[1], NEVEROVA[0])}
    ed.append_to_section(method_head, [t.format(**n) for t in method])
    anchor = ed.heading(next_head)
    ed.heading_before(anchor, head, 2)
    for t in res[:2]:
        ed.body_paragraph_before(anchor, t)
    add_table(ed, anchor, rows, cap)
    ed.body_paragraph_before(anchor, res[2])
    try:
        ed.save()
        print(path, "updated")
    except PermissionError:
        print(path, "LOCKED (open in Word) - not updated")
