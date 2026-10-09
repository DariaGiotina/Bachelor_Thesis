"""Questionnaire-only baseline (E1 arm 2): method in thesis 5.8 / paper 3.8, first results in thesis 8.1 / paper 4.1."""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocEditor  # noqa: E402

MLP = ("https://www.deeplearningbook.org/",
       "I. Goodfellow, Y. Bengio, A. Courville, Deep Learning, MIT Press 2016, chapter 6 (deep feedforward networks)")

METHOD_RO = (
    "Al doilea braț al experimentului E1 este modelul doar cu chestionar (`ml/models/q_model.py`, rulat de "
    "`ml/run_q_only.py`), care arată cât semnal conține chestionarul singur, fără fotografie. Este un perceptron "
    "multistrat (multilayer perceptron, MLP) [{mlp}]: o rețea formată din straturi liniare succesive, fiecare urmat "
    "de o funcție de activare ReLU (care păstrează valorile pozitive și le înlocuiește pe cele negative cu 0) și de "
    "dropout 0,2 (în antrenare, 20% dintre neuroni sunt ignorați la întâmplare, ca rețeaua să nu memoreze exemplele). "
    "Intrarea este vectorul răspunsurilor codificate (40 de valori) alăturat măștii de valori lipsă (6 valori, câte una "
    "pe întrebare), astfel încât rețeaua poate deosebi un răspuns „nu” de o întrebare la care nu s-a răspuns; urmează "
    "două straturi ascunse de câte 64 de neuroni și un strat de ieșire cu patru valori. Modelul folosește exact aceleași "
    "cazuri, împărțiri, seed-uri, pierdere ponderată pe clase, oprire timpurie pe macro-F1 de validare și protocol de "
    "evaluare ca modelul cu imagine. Setul de test este evaluat și cu o proporție r din răspunsuri ascunse (r = 0; 0,25; "
    "0,5; 0,75; 1), iar răspunsurile ascunse sunt exact aceleași ca la evaluarea modelului cu fuziune, deci curbele pot "
    "fi comparate direct."
)
METHOD_EN = (
    "The second arm of experiment E1 is the questionnaire-only model (`ml/models/q_model.py`, run by "
    "`ml/run_q_only.py`), which shows how much signal the questionnaire carries on its own, without the photo. It is a "
    "multilayer perceptron (MLP) [{mlp}]: a network of successive linear layers, each followed by a ReLU activation "
    "(which keeps positive values and replaces negative ones with 0) and dropout 0.2 (during training, 20% of the "
    "neurons are ignored at random so the network does not memorise the examples). The input is the vector of encoded "
    "answers (40 values) next to the missingness mask (6 values, one per question), so the network can tell an answer "
    "'no' from a question that was not answered; it is followed by two hidden layers of 64 neurons and an output layer "
    "with four values. The model uses exactly the same cases, splits, seeds, class-weighted loss, early stopping on "
    "validation macro-F1 and evaluation protocol as the photo model. The test set is also scored with a share r of the "
    "answers hidden (r = 0, 0.25, 0.5, 0.75, 1), and the hidden answers are exactly the same as in the fusion model's "
    "evaluation, so the curves can be compared directly."
)

RES_RO = [
    "Pe cele cinci seed-uri, modelul doar cu chestionar obține pe test macro-F1 0,390 ± 0,038 (medie ± abatere "
    "standard), acuratețe echilibrată 0,443 ± 0,043 și ECE 0,083 ± 0,020 (Tabelul 8.1). Antrenarea durează 6–11 secunde "
    "pe seed, iar oprirea timpurie alege epoci între 16 și 51. Pe categorii, F1 este 0,569 pentru eczema_dermatitis, "
    "0,429 pentru normal_other, 0,343 pentru redness_rosacea și 0,218 pentru acne. Pentru redness_rosacea setul de test "
    "are în medie doar 6 cazuri, deci valoarea este foarte nesigură (abatere standard 0,112). Chestionarul conține așadar "
    "semnal clar peste nivelul întâmplării, dar insuficient pentru a separa acneea, care pe baza răspunsurilor seamănă "
    "cu celelalte probleme.",
    "Când răspunsurile sunt ascunse, performanța scade constant: macro-F1 0,390 cu răspunsurile naturale, 0,325 cu 25% "
    "ascunse, 0,264 cu 50%, 0,221 cu 75% și 0,145 cu toate ascunse. Fără niciun răspuns, modelul dă aceeași categorie "
    "tuturor cazurilor (la seed-ul 0, normal_other), iar acuratețea echilibrată este exact 0,250, adică nivelul "
    "întâmplării pentru patru categorii. Acest rezultat confirmă că masca de valori lipsă funcționează așa cum s-a "
    "proiectat: un chestionar gol nu aduce nicio informație falsă.",
    "Pe tonuri de piele (eFST), macro-F1 este 0,401 ± 0,045 pentru I–II (117 cazuri în medie), 0,342 ± 0,100 pentru "
    "III–IV (120 de cazuri) și 0,475 ± 0,131 pentru V–VI (23 de cazuri). Grupul cel mai defavorizat este III–IV la trei "
    "seed-uri și I–II la două, cu macro-F1 mediu 0,319 ± 0,067. Valoarea mai mare pentru V–VI nu trebuie interpretată "
    "ca un avantaj: grupul are puțin peste 20 de cazuri, iar abaterea standard între seed-uri (0,131) este mai mare "
    "decât diferențele dintre grupuri. Aceste valori sunt referința inferioară cu care vor fi comparate modelul doar cu "
    "imagine și modelul cu fuziune (RQ1).",
]
RES_EN = [
    "Over the five seeds, the questionnaire-only model reaches a test macro-F1 of 0.390 ± 0.038 (mean ± standard "
    "deviation), balanced accuracy 0.443 ± 0.043 and ECE 0.083 ± 0.020 (Table 1). Training takes 6-11 seconds per seed, "
    "and early stopping selects epochs between 16 and 51. Per category, F1 is 0.569 for eczema_dermatitis, 0.429 for "
    "normal_other, 0.343 for redness_rosacea and 0.218 for acne. The redness_rosacea test set has only 6 cases on "
    "average, so that value is very uncertain (standard deviation 0.112). The questionnaire thus carries clear signal "
    "above chance, but not enough to separate acne, which looks like the other concerns from the answers alone.",
    "When answers are hidden, performance falls steadily: macro-F1 0.390 with the natural answers, 0.325 with 25% "
    "hidden, 0.264 with 50%, 0.221 with 75% and 0.145 with all hidden. With no answers at all, the model gives every "
    "case the same category (normal_other for seed 0) and balanced accuracy is exactly 0.250, the chance level for four "
    "categories. This confirms that the missingness mask works as designed: an empty questionnaire adds no false "
    "information.",
    "By skin tone (eFST), macro-F1 is 0.401 ± 0.045 for I-II (117 cases on average), 0.342 ± 0.100 for III-IV (120 "
    "cases) and 0.475 ± 0.131 for V-VI (23 cases). The worst group is III-IV in three seeds and I-II in two, with a mean "
    "macro-F1 of 0.319 ± 0.067. The higher value for V-VI should not be read as an advantage: the group has just over 20 "
    "cases, and the spread across seeds (0.131) is larger than the differences between groups. These values are the "
    "lower reference against which the photo-only and fusion models will be compared (RQ1).",
]
ROWS = [["% răspunsuri ascunse", "Macro-F1", "Acuratețe echilibrată"],
        ["0 (naturale)", "0,390 ± 0,038", "0,443 ± 0,043"], ["25", "0,325 ± 0,038", "-"],
        ["50", "0,264 ± 0,047", "-"], ["75", "0,221 ± 0,037", "-"], ["100", "0,145 ± 0,037", "0,250 ± 0,000"]]


def table_rows(ro: bool):
    if ro:
        return ROWS
    return [["% answers hidden", "Macro-F1", "Balanced accuracy"]] + [
        [r[0].replace("naturale", "natural"), r[1].replace(",", "."), r[2].replace(",", ".")] for r in ROWS[1:]]


def add_table(ed: DocEditor, anchor, rows, caption: str):
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


for path, method_head, res_head, next_head, method, res, cap, ro in (
        ("Teza_Licenta.docx", "5.8 Modelul și fuziunea multimodală", "8.1 Modelul doar cu chestionar (E1, brațul 2)",
         "Capitolul 9. Concluzii și direcții viitoare", METHOD_RO, RES_RO,
         "Tabelul 8.1. Modelul doar cu chestionar pe test (5 seed-uri, medie ± abatere standard), după proporția de "
         "răspunsuri ascunse.", True),
        ("Paper_Skin_Concern.docx", "3.8 Model and training", "4.1 Questionnaire-only baseline (E1, arm 2)",
         "5. Discussion", METHOD_EN, RES_EN,
         "Table 1. Questionnaire-only model on the test set (5 seeds, mean ± standard deviation) by share of hidden "
         "answers.", False)):
    ed = DocEditor(str(ROOT / "docs" / path))
    if ed.has_heading(res_head):
        print(path, "already updated")
        continue
    n = ed.add_reference(MLP[1], MLP[0])
    ed.append_to_section(method_head, [method.format(mlp=n)])
    anchor = ed.heading(next_head)
    ed.heading_before(anchor, res_head, 2)
    ed.body_paragraph_before(anchor, res[0])
    add_table(ed, anchor, table_rows(ro), cap)
    for text in res[1:]:
        ed.body_paragraph_before(anchor, text)
    try:
        ed.save()
        print(path, "updated")
    except PermissionError:
        print(path, "LOCKED (open in Word) - not updated")
