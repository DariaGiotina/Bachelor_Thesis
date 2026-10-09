"""Task 3.3: E1 runner results (gated, FiLM, no-dropout, ensemble) in thesis 8.3 / paper 4.3; ECE CI fix in 5.10 / 3.9."""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocEditor  # noqa: E402

ROELOFS = ("https://arxiv.org/abs/2012.08668",
           "R. Roelofs, N. Cain, J. Shlens, M. C. Mozer, Mitigating Bias in Calibration Error Estimation, AISTATS 2022")
GENEST = ("https://doi.org/10.1214/ss/1177013825",
          "C. Genest, J. V. Zidek, Combining Probability Distributions: A Critique and an Annotated Bibliography, "
          "Statistical Science 1(1), 1986")

ECE_RO = (
    "Intervalul de încredere al ECE necesită o corecție. Prin reeșantionarea cazurilor cu înlocuire, fiecare interval "
    "de încredere conține mai puține cazuri distincte, diferența dintre acuratețe și încredere devine mai zgomotoasă și, "
    "fiind o valoare absolută, nu poate fi negativă; de aceea ECE calculat pe eșantioanele bootstrap este în medie mai "
    "mare decât cel calculat pe setul de test (eroare sistematică, bias) [{roelofs}]. Intervalul percentil obișnuit se "
    "deplasează astfel în sus și, după medierea pe cinci seed-uri, poate chiar să nu mai conțină valoarea estimată. "
    "Pentru ECE se folosește de aceea intervalul percentil deplasat cu bias-ul bootstrap (media eșantioanelor minus "
    "valoarea estimată); pentru celelalte metrici rămâne intervalul percentil."
)
ECE_EN = (
    "The ECE confidence interval needs a correction. When cases are resampled with replacement, each confidence bin "
    "holds fewer distinct cases, the gap between accuracy and confidence becomes noisier and, being an absolute value, "
    "cannot be negative; the ECE of bootstrap samples is therefore larger on average than the ECE of the test set "
    "(a bias) [{roelofs}]. The usual percentile interval is thus shifted upward and, after averaging over five seeds, "
    "may not even contain the estimate. For ECE we therefore use the percentile interval shifted by the bootstrap bias "
    "(mean of the samples minus the estimate); the other metrics keep the percentile interval."
)

RES_RO = [
    "Pentru a afla dacă rezultatul precedent ține de arhitectura fuziunii, scriptul `ml/run_e1.py` antrenează pe "
    "aceleași cinci seed-uri încă trei variante: fuziunea cu poartă, fuziunea FiLM și fuziunea prin concatenare fără "
    "modality dropout. Se adaugă și un ansamblu (ensemble) al celor două modele antrenate separat: probabilitățile "
    "modelului doar cu imagine și ale celui doar cu chestionar sunt combinate prin medie geometrică ponderată "
    "(log-linear pooling) [{genest}], p ∝ p_imagine^w · p_chestionar^(1−w), cu ponderea w aleasă pe setul de validare "
    "dintre 0; 0,1; ...; 1, fără reantrenare. Dacă ansamblul ar depăși modelul doar cu imagine, ar însemna că "
    "chestionarul conține informație pe care fotografia nu o are, dar modelele antrenate împreună nu o folosesc. Toate "
    "modelele sunt testate pe exact aceleași cazuri, iar diferențele sunt calculate pereche, pe aceleași cazuri, cu "
    "intervale de încredere bootstrap stratificate pe seed (cazurile sunt reeșantionate în setul de test al fiecărui "
    "seed, iar diferența este mediată pe seed-uri). Rezultatele sunt în Tabelul 8.3 și în fișierele "
    "`ml/results/e1/e1_summary.csv` și `e1_table.md`.",
    "Niciuna dintre variante nu depășește semnificativ modelul doar cu imagine (macro-F1 0,537 ± 0,038). Fuziunea "
    "FiLM obține cel mai bun rezultat, 0,544 ± 0,043, dar diferența față de imagine este +0,008 (IÎ 95% −0,023 ... "
    "+0,038; mai bună la 3 din 5 seed-uri). Fuziunea cu poartă obține 0,514 ± 0,040 (−0,023 [−0,060; +0,011]), iar "
    "ansamblul 0,521 ± 0,035 (−0,016 [−0,053; +0,018]). Fuziunea prin concatenare fără modality dropout este singura "
    "variantă semnificativ mai slabă decât imaginea: 0,503 ± 0,046, diferență −0,033 [−0,067; −0,002], mai slabă la "
    "toate cele 5 seed-uri. Prin urmare, ipoteza că ascunderea răspunsurilor în antrenare ar fi împiedicat folosirea "
    "chestionarului nu se confirmă: fără ea rezultatul este chiar mai slab.",
    "Testul cu chestionarul ascuns confirmă imaginea de ansamblu: cu toate răspunsurile ascunse, macro-F1 rămâne "
    "practic același pentru concatenare (0,506), poartă (0,521) și FiLM (0,518). Doar FiLM pierde ceva (0,544 → "
    "0,518), deci este singura variantă care folosește puțin chestionarul. La ansamblu, ponderea aleasă pe validare a "
    "dat chestionarului un rol la trei seed-uri, dar câștigul observat pe validare nu s-a regăsit pe test, ceea ce "
    "arată că avantajul de pe validare era zgomot. Concluzia pentru RQ1 în această configurație este că pe SCIN, cu "
    "chestionarul codificat astfel, răspunsurile nu aduc informație măsurabilă în plus față de fotografie pentru cele "
    "patru categorii, deși singure au semnal clar (0,390 față de nivelul întâmplării). O explicație posibilă este că "
    "o parte din informația chestionarului (de exemplu zona corpului sau aspectul leziunii) este deja vizibilă în "
    "fotografie. Rezultatul este limitat de dimensiunea setului (circa 1.270 de cazuri de antrenare, 270 de test pe "
    "seed) și de cele cinci seed-uri, care pot detecta doar diferențe de ordinul a 0,03–0,04 macro-F1.",
]
RES_EN = [
    "To find out whether the previous result depends on the fusion architecture, `ml/run_e1.py` trains three more "
    "variants on the same five seeds: gated fusion, FiLM fusion and concatenation fusion without modality dropout. We "
    "also add an ensemble of the two separately trained models: the probabilities of the photo-only and the "
    "questionnaire-only model are combined by a weighted geometric mean (log-linear pooling) [{genest}], "
    "p ∝ p_photo^w · p_questionnaire^(1−w), with the weight w chosen on the validation set from 0, 0.1, ..., 1, without "
    "retraining. If the ensemble beat the photo-only model, the questionnaire would hold information the photo lacks but "
    "the jointly trained models fail to use. All models are tested on exactly the same cases, and differences are "
    "computed pairwise on those cases with seed-stratified bootstrap confidence intervals (cases are resampled within "
    "each seed's test set and the difference is averaged over seeds). Results are in Table 3 and in "
    "`ml/results/e1/e1_summary.csv` and `e1_table.md`.",
    "None of the variants is significantly better than the photo-only model (macro-F1 0.537 ± 0.038). FiLM fusion "
    "scores best, 0.544 ± 0.043, but its difference from the photo model is +0.008 (95% CI −0.023 to +0.038; better in "
    "3 of 5 seeds). Gated fusion reaches 0.514 ± 0.040 (−0.023 [−0.060, +0.011]) and the ensemble 0.521 ± 0.035 "
    "(−0.016 [−0.053, +0.018]). Concatenation fusion without modality dropout is the only variant significantly worse "
    "than the photo: 0.503 ± 0.046, difference −0.033 [−0.067, −0.002], worse in all 5 seeds. The hypothesis that "
    "hiding answers during training prevented the use of the questionnaire is therefore not supported: without it the "
    "result is even worse.",
    "The hidden-questionnaire test confirms the overall picture: with all answers hidden, macro-F1 stays practically the "
    "same for concatenation (0.506), gated (0.521) and FiLM fusion (0.518). Only FiLM loses something (0.544 → 0.518), "
    "so it is the only variant that uses the questionnaire a little. For the ensemble, the weight chosen on validation "
    "gave the questionnaire a role in three seeds, but the gain seen on validation did not carry over to the test set, "
    "showing that the validation advantage was noise. The conclusion for RQ1 in this configuration is that on SCIN, "
    "with the questionnaire encoded this way, the answers add no measurable information beyond the photo for the four "
    "categories, although on their own they carry clear signal (0.390 versus chance). A possible explanation is that "
    "part of the questionnaire's information (e.g. body area or lesion texture) is already visible in the photo. The "
    "result is limited by the size of the set (about 1,270 training and 270 test cases per seed) and by the five seeds, "
    "which can only detect differences of about 0.03-0.04 macro-F1.",
]
HEAD = ["Model", "Macro-F1", "IÎ 95%", "Diferență față de imagine [IÎ 95%]", "Macro-F1, răspunsuri ascunse"]
HEAD_EN = ["Model", "Macro-F1", "95% CI", "Difference vs photo [95% CI]", "Macro-F1, answers hidden"]
DATA = [
    ("Doar imagine", "Photo only", "0.537 ± 0.038", "[0.493, 0.572]", "-", "-"),
    ("Doar chestionar", "Questionnaire only", "0.390 ± 0.038", "[0.344, 0.428]", "-0.147 [-0.199, -0.096]", "0.145"),
    ("Fuziune concat", "Fusion concat", "0.516 ± 0.057", "[0.468, 0.551]", "-0.021 [-0.051, +0.007]", "0.506"),
    ("Fuziune cu poartă", "Fusion gated", "0.514 ± 0.040", "[0.464, 0.550]", "-0.023 [-0.060, +0.011]", "0.521"),
    ("Fuziune FiLM", "Fusion FiLM", "0.544 ± 0.043", "[0.497, 0.579]", "+0.008 [-0.023, +0.038]", "0.518"),
    ("Concat fără dropout", "Concat, no dropout", "0.503 ± 0.046", "[0.456, 0.538]", "-0.033 [-0.067, -0.002]", "0.495"),
    ("Ansamblu imagine × chestionar", "Ensemble photo × questionnaire", "0.521 ± 0.035", "[0.470, 0.556]",
     "-0.016 [-0.053, +0.018]", "0.549"),
]


def ro(s: str) -> str:
    return s.replace(".", ",").replace(", ", "; ") if any(ch.isdigit() for ch in s) else s


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


for path, method_head, head, next_head, ece, res, rows, cap in (
        ("Teza_Licenta.docx", "5.10 Protocolul de evaluare", "8.3 Variante de fuziune și ansamblu: aduce chestionarul "
         "informație nouă?", "Capitolul 9. Concluzii și direcții viitoare", ECE_RO, RES_RO,
         [HEAD] + [[d[0], ro(d[2]), ro(d[3]), ro(d[4]), ro(d[5])] for d in DATA],
         "Tabelul 8.3. Toate brațele E1 pe test (EfficientNet-B0, pierdere ponderată, 5 seed-uri; medie ± abatere "
         "standard, interval de încredere bootstrap stratificat pe seed; diferențe pereche pe aceleași cazuri)."),
        ("Paper_Skin_Concern.docx", "3.9 Evaluation protocol", "4.3 Fusion variants and ensemble: does the "
         "questionnaire add information?", "5. Discussion", ECE_EN, RES_EN,
         [HEAD_EN] + [[d[1], d[2], d[3], d[4], d[5]] for d in DATA],
         "Table 3. All E1 arms on the test set (EfficientNet-B0, weighted loss, 5 seeds; mean ± standard deviation, "
         "seed-stratified bootstrap confidence interval; paired differences on the same cases).")):
    ed = DocEditor(str(ROOT / "docs" / path))
    if ed.has_heading(head):
        print(path, "already updated")
        continue
    n = {"roelofs": ed.add_reference(ROELOFS[1], ROELOFS[0]), "genest": ed.add_reference(GENEST[1], GENEST[0])}
    ed.append_to_section(method_head, [ece.format(**n)])
    anchor = ed.heading(next_head)
    ed.heading_before(anchor, head, 2)
    ed.body_paragraph_before(anchor, res[0].format(**n))
    add_table(ed, anchor, rows, cap)
    for t in res[1:]:
        ed.body_paragraph_before(anchor, t)
    try:
        ed.save()
        print(path, "updated")
    except PermissionError:
        print(path, "LOCKED (open in Word) - not updated")
