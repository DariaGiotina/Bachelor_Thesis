"""First E1 comparison (photo-only vs late fusion vs questionnaire-only): thesis 8.2 / paper 4.2."""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocEditor  # noqa: E402

TTEST = ("https://doi.org/10.1093/biomet/6.1.1", "Student (W. S. Gosset), The Probable Error of a Mean, "
         "Biometrika 6(1), 1908")

RO = [
    "Prima comparație completă a experimentului E1 folosește EfficientNet-B0, pierderea ponderată pe clase și aceleași "
    "cinci seed-uri pentru toate cele trei brațe (Tabelul 8.2). Modelul doar cu imagine obține macro-F1 0,537 ± 0,038, "
    "modelul cu fuziune prin concatenare 0,516 ± 0,057, iar modelul doar cu chestionar 0,390 ± 0,038. Pentru a compara "
    "două modele pe aceleași seed-uri se folosește un test pereche (paired test): pentru fiecare seed se calculează "
    "diferența dintre cele două modele, iar testul verifică dacă media diferențelor este diferită de 0. Diferența "
    "fuziune minus imagine este −0,021 ± 0,031, iar testul t pereche [{t}] dă p = 0,20 (testul Wilcoxon, care nu "
    "presupune o distribuție normală, dă p = 0,31). Valoarea p este probabilitatea de a obține o diferență cel puțin "
    "atât de mare dacă, în realitate, modelele ar fi la fel de bune; o valoare peste 0,05 înseamnă că diferența nu este "
    "semnificativă statistic. Cu doar cinci seed-uri testul are putere mică, deci rezultatul arată că, în această "
    "configurație, chestionarul nu îmbunătățește clasificarea, nu că o înrăutățește.",
    "Două observații pot explica rezultatul (ipoteze încă netestate). Mai întâi, modelul cu fuziune aproape că nu folosește chestionarul: macro-F1 "
    "rămâne între 0,506 și 0,518 indiferent dacă sunt ascunse 0%, 25%, 50%, 75% sau 100% din răspunsuri, deși "
    "chestionarul singur conține semnal (0,390). Ramura de imagine (1.280 de trăsături) domină ramura chestionarului "
    "(64 de trăsături) în stratul de concatenare, iar ascunderea chestionarului în 30% din exemple în timpul antrenării "
    "îi reduce și mai mult contribuția. În al doilea rând, la trei din cinci seed-uri punctul de control ales pentru "
    "fuziune provine din etapa 1, din primele trei epoci, deci rețeaua nu a beneficiat de reantrenarea straturilor "
    "superioare; macro-F1 pe validare, calculat pe circa 270 de cazuri, variază mult de la o epocă la alta, iar "
    "selecția pe validare este zgomotoasă. Pe tonuri de piele, ambele modele sunt cele mai slabe pe grupul eFST V–VI "
    "(imagine 0,490 ± 0,175, fuziune 0,445 ± 0,085, circa 23 de cazuri), cu cel mai slab grup V–VI la trei seed-uri "
    "pentru modelul cu imagine. Pașii următori sunt variantele de fuziune cu poartă și FiLM, care pot da chestionarului "
    "o influență mai mare, și antrenarea fără modality dropout (E2), pentru a separa efectul arhitecturii de cel al "
    "ascunderii răspunsurilor.",
]
EN = [
    "The first complete E1 comparison uses EfficientNet-B0, the class-weighted loss and the same five seeds for all "
    "three arms (Table 2). The photo-only model reaches a macro-F1 of 0.537 ± 0.038, the concatenation fusion model "
    "0.516 ± 0.057 and the questionnaire-only model 0.390 ± 0.038. To compare two models on the same seeds we use a "
    "paired test: for each seed the difference between the two models is computed, and the test checks whether the "
    "mean difference differs from 0. The fusion minus photo difference is −0.021 ± 0.031, and the paired t-test [{t}] "
    "gives p = 0.20 (the Wilcoxon signed-rank test, which does not assume a normal distribution, gives p = 0.31). The "
    "p-value is the probability of a difference at least this large if the models were in fact equally good; a value "
    "above 0.05 means the difference is not statistically significant. With only five seeds the test has little power, "
    "so the result shows that in this configuration the questionnaire does not improve classification, not that it "
    "harms it.",
    "Two observations may explain the result (hypotheses not yet tested). First, the fusion model hardly uses the questionnaire: macro-F1 stays between "
    "0.506 and 0.518 whether 0%, 25%, 50%, 75% or 100% of the answers are hidden, although the questionnaire alone "
    "carries signal (0.390). The image branch (1,280 features) dominates the questionnaire branch (64 features) in the "
    "concatenation layer, and hiding the questionnaire in 30% of training samples reduces its contribution further. "
    "Second, for three of the five seeds the selected fusion checkpoint comes from stage 1, within the first three "
    "epochs, so the network did not benefit from fine-tuning the upper layers; validation macro-F1, computed on about "
    "270 cases, varies a lot from epoch to epoch, so selection on validation is noisy. By skin tone, both models are "
    "weakest on eFST V-VI (photo 0.490 ± 0.175, fusion 0.445 ± 0.085, about 23 cases), with V-VI the worst group in "
    "three seeds for the photo model. The next steps are the gated and FiLM fusion variants, which can give the "
    "questionnaire more influence, and training without modality dropout (E2), to separate the effect of the "
    "architecture from that of hiding answers.",
]
ROWS_RO = [["Model (EfficientNet-B0, 5 seed-uri)", "Macro-F1", "Acuratețe echilibrată", "ECE", "eFST V–VI macro-F1"],
           ["Doar imagine", "0,537 ± 0,038", "0,624 ± 0,044", "0,070 ± 0,012", "0,490 ± 0,175"],
           ["Fuziune (concat)", "0,516 ± 0,057", "0,595 ± 0,038", "0,088 ± 0,056", "0,445 ± 0,085"],
           ["Doar chestionar", "0,390 ± 0,038", "0,443 ± 0,043", "0,083 ± 0,020", "0,475 ± 0,131"]]
ROWS_EN = [["Model (EfficientNet-B0, 5 seeds)", "Macro-F1", "Balanced accuracy", "ECE", "eFST V-VI macro-F1"],
           ["Photo only", "0.537 ± 0.038", "0.624 ± 0.044", "0.070 ± 0.012", "0.490 ± 0.175"],
           ["Fusion (concat)", "0.516 ± 0.057", "0.595 ± 0.038", "0.088 ± 0.056", "0.445 ± 0.085"],
           ["Questionnaire only", "0.390 ± 0.038", "0.443 ± 0.043", "0.083 ± 0.020", "0.475 ± 0.131"]]


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


for path, head, next_head, paras, rows, cap in (
        ("Teza_Licenta.docx", "8.2 Imagine, fuziune și chestionar: prima comparație (E1)",
         "Capitolul 9. Concluzii și direcții viitoare", RO, ROWS_RO,
         "Tabelul 8.2. Rezultate pe test ale celor trei brațe E1 (medie ± abatere standard pe 5 seed-uri, toate "
         "răspunsurile disponibile)."),
        ("Paper_Skin_Concern.docx", "4.2 Photo, fusion and questionnaire: first comparison (E1)", "5. Discussion",
         EN, ROWS_EN,
         "Table 2. Test results of the three E1 arms (mean ± standard deviation over 5 seeds, all answers available).")):
    ed = DocEditor(str(ROOT / "docs" / path))
    if ed.has_heading(head):
        print(path, "already updated")
        continue
    n = ed.add_reference(TTEST[1], TTEST[0])
    anchor = ed.heading(next_head)
    ed.heading_before(anchor, head, 2)
    ed.body_paragraph_before(anchor, paras[0].format(t=n))
    add_table(ed, anchor, rows, cap)
    ed.body_paragraph_before(anchor, paras[1])
    try:
        ed.save()
        print(path, "updated")
    except PermissionError:
        print(path, "LOCKED (open in Word) - not updated")
