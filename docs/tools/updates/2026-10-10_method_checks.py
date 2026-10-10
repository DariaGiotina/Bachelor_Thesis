"""Is the questionnaire null result caused by the method? Positive control, cross-fitted stacking, ceiling.

New thesis 8.7 / paper 4.7.
"""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocEditor  # noqa: E402

WANG = ("https://arxiv.org/abs/1905.12681",
        "W. Wang, D. Tran, M. Feiszli, What Makes Training Multi-Modal Classification Networks Hard?, CVPR 2020")
WOLPERT = ("https://doi.org/10.1016/S0893-6080(05)80023-1",
           "D. H. Wolpert, Stacked generalization, Neural Networks 5(2), 1992")

RO = [
    "Secțiunile 8.4–8.6 arată că niciun model nu câștigă din chestionar și că modelul de fuziune nu îl folosește deloc "
    "(ascunderea tuturor răspunsurilor nu costă nimic), deși chestionarul singur este clar peste nivelul întâmplării "
    "(macro-F1 0,381 față de 0,25 pentru o ghicire la întâmplare între patru categorii). Înainte de a atribui rezultatul "
    "datelor, trebuie exclusă o eroare de metodă. O cauză cunoscută în învățarea multimodală este că ramura cea mai "
    "puternică (aici imaginea) ajunge să încadreze aproape perfect cazurile de antrenare, astfel că pe datele de "
    "antrenare cealaltă sursă pare inutilă și stratul de fuziune învață să o ignore [{wang}]. Au fost făcute trei "
    "verificări suplimentare.",
    "(1) Control pozitiv. Un control pozitiv este un test în care rezultatul corect este cunoscut dinainte, folosit "
    "pentru a verifica dacă metoda îl poate detecta. Chestionarului real i s-a adăugat o întrebare sintetică al cărei "
    "răspuns este categoria adevărată pentru o proporție a („acord”) din cazuri și o categorie aleatoare în rest, fixă "
    "pentru fiecare caz (`ml/analysis/fusion_positive_control.py`; trei seed-uri). Erorile acestei întrebări sunt "
    "independente de fotografie prin construcție, deci informația ei este complet complementară. La a = 0,5 "
    "(întrebarea singură: macro-F1 0,50) modelul de fuziune crește de la 0,527 la 0,635 (+0,108), deci procedura de "
    "antrenare poate folosi chestionarul atunci când acesta este suficient de informativ: nu există o eroare de "
    "implementare. La a = 0,3, însă, întrebarea singură are macro-F1 0,380, aproape exact cât chestionarul real, iar "
    "câștigul fuziunii este doar +0,005.",
    "(2) Stivuire cu validare încrucișată (cross-fitted stacking) [{wolpert}]. Stivuirea înseamnă combinarea "
    "predicțiilor unor modele deja antrenate de către un al doilea model, mic. Pentru ca fotografia să nu pară mai "
    "sigură decât este, setul de antrenare al fiecărui seed a fost împărțit în cinci părți (fold-uri) cu aceeași "
    "distribuție a categoriilor; pentru fiecare parte, un model doar cu imagine a fost antrenat pe celelalte patru și "
    "a prezis partea lăsată deoparte. Astfel fiecare caz de antrenare primește o predicție „din afara fold-ului” "
    "(out-of-fold), făcută de un model care nu l-a văzut, la fel de onestă ca o predicție pe test. Combinatorul este o "
    "regresie logistică multinomială (un model liniar care transformă intrările în probabilități pentru cele patru "
    "categorii), cu ponderi de clasă echilibrate și cu tăria regularizării C (penalizarea coeficienților mari; un C "
    "mic înseamnă un model mai simplu) aleasă pe validare (`ml/run_stacking.py`; zece seed-uri). Patru variante "
    "folosesc exact aceleași predicții ale fotografiei, deci diferența dintre ele izolează contribuția chestionarului: "
    "doar fotografia, fotografia plus răspunsurile brute, fotografia plus probabilitățile unui MLP pe chestionar "
    "antrenat tot out-of-fold, și doar chestionarul. Spre deosebire de fuziune, aceste modele folosesc efectiv "
    "chestionarul (ascunderea răspunsurilor le schimbă rezultatul), dar nu câștigă din el (Tabelul 8.7): fotografia "
    "plus răspunsurile -0,020 [-0,044; +0,006], fotografia plus MLP -0,005 [-0,020; +0,011] față de combinatorul doar "
    "cu fotografia. Combinatorul doar cu fotografia este puțin sub modelul doar cu imagine din E1 (-0,023), deoarece "
    "fiecare model de fold vede doar 80% din cazurile de antrenare.",
    "(3) Plafonul câștigului. Întrebarea sintetică a fost pusă și în combinatorul de stivuire, pe aceleași predicții "
    "out-of-fold (`ml/analysis/stacking_synthetic_ceiling.py`; zece seed-uri). Este cazul cel mai favorabil posibil: "
    "o întrebare de o anumită tărie, cu erori complet independente de fotografie. Rezultatul dă plafonul câștigului: "
    "la tăria chestionarului real (a = 0,3, întrebarea singură 0,363) câștigul este doar +0,017 ± 0,036 (mai bun în "
    "6 din 10 seed-uri); la a = 0,4 (0,417) +0,039 (8/10), la a = 0,5 (0,485) +0,081 (10/10).",
    "Concluzia este că rezultatul nul nu provine dintr-o eroare de metodă, ci din date. O întrebare de tăria "
    "chestionarului SCIN poate aduce, chiar și în cazul ideal al independenței complete față de fotografie, cel mult "
    "aproximativ 0,02 macro-F1, iar diferențe de această mărime nu pot fi detectate cu circa 270 de cazuri de test pe "
    "seed. Răspunsurile reale sunt mai slabe decât acest ideal, deoarece greșesc mai ales pe aceleași cazuri ca "
    "fotografia (secțiunea 8.5). Pentru un câștig măsurabil ar fi nevoie de întrebări mai informative (de exemplu "
    "macro-F1 de cel puțin 0,42 singure și puțin corelate cu fotografia) sau de un set de date mult mai mare. Pentru "
    "lucrare, acesta este un rezultat util: arată de ce chestionarul nu ajută și ce ar trebui să îndeplinească un "
    "chestionar ca să ajute.",
]
EN = [
    "Sections 4.4-4.6 show that no model gains from the questionnaire and that the fusion model does not use it at all "
    "(hiding every answer costs nothing), although the questionnaire alone is clearly above chance (macro-F1 0.381 "
    "versus 0.25 for random guessing among four categories). Before attributing the result to the data, a method error "
    "must be ruled out. A known cause in multimodal learning is that the stronger branch (here the image) comes to fit "
    "the training cases almost perfectly, so on the training data the other source looks useless and the fusion layer "
    "learns to ignore it [{wang}]. Three further checks were run.",
    "(1) Positive control. A positive control is a test whose correct outcome is known in advance, used to check that "
    "the method can detect it. A synthetic question was appended to the real questionnaire; its answer is the true "
    "category for a share a ('agreement') of the cases and a random category otherwise, fixed per case "
    "(`ml/analysis/fusion_positive_control.py`; three seeds). Its errors are independent of the photo by construction, "
    "so its information is fully complementary. At a = 0.5 (question alone: macro-F1 0.50) the fusion model rises from "
    "0.527 to 0.635 (+0.108), so the training procedure can use the questionnaire when it is informative enough: there "
    "is no implementation error. At a = 0.3, however, the question alone has macro-F1 0.380, almost exactly that of the "
    "real questionnaire, and the fusion gain is only +0.005.",
    "(2) Cross-fitted stacking [{wolpert}]. Stacking means combining the predictions of already trained models with a "
    "second, small model. So that the photo does not look more reliable than it is, the training set of each seed was "
    "split into five parts (folds) with the same category distribution; for each part, a photo-only model was trained "
    "on the other four and predicted the held-out part. Every training case thus gets an out-of-fold prediction from a "
    "model that never saw it, as honest as a test prediction. The combiner is a multinomial logistic regression (a "
    "linear model that turns its inputs into probabilities for the four categories) with balanced class weights and "
    "regularisation strength C (a penalty on large coefficients; a small C means a simpler model) chosen on validation "
    "(`ml/run_stacking.py`; ten seeds). Four variants use exactly the same photo predictions, so their difference "
    "isolates the questionnaire's contribution: photo only, photo plus raw answers, photo plus the probabilities of a "
    "questionnaire MLP also trained out-of-fold, and questionnaire only. Unlike fusion, these models do use the "
    "questionnaire (hiding answers changes their output), but they do not gain from it (Table 6): photo plus answers "
    "-0.020 [-0.044, +0.006], photo plus MLP -0.005 [-0.020, +0.011] against the photo-only combiner. The photo-only "
    "combiner is slightly below the E1 photo-only model (-0.023) because each fold model sees only 80% of the training "
    "cases.",
    "(3) Ceiling of the gain. The synthetic question was also put into the stacking combiner, on the same out-of-fold "
    "predictions (`ml/analysis/stacking_synthetic_ceiling.py`; ten seeds). This is the most favourable case possible: a "
    "question of a given strength whose errors are fully independent of the photo. It gives the ceiling of the gain: at "
    "the strength of the real questionnaire (a = 0.3, question alone 0.363) the gain is only +0.017 ± 0.036 (better in "
    "6 of 10 seeds); at a = 0.4 (0.417) +0.039 (8/10), at a = 0.5 (0.485) +0.081 (10/10).",
    "The conclusion is that the null result does not come from a method error but from the data. A question as strong "
    "as the SCIN questionnaire can add, even in the ideal case of full independence from the photo, at most about 0.02 "
    "macro-F1, and differences of that size cannot be detected with about 270 test cases per seed. The real answers are "
    "weaker than this ideal, because they mostly fail on the same cases as the photo (Section 4.5). A measurable gain "
    "would need more informative questions (e.g. a macro-F1 of at least 0.42 on their own and little correlation with "
    "the photo) or a much larger dataset. For the paper this is a useful result: it explains why the questionnaire does "
    "not help and what a questionnaire would have to achieve in order to help.",
]

DATA = [  # arm, macro-F1 mean ± sd, difference vs reference [95% CI], seeds better, reference
    ["Positive control, fusion + synthetic a = 0.5 (3 seeds)", "0.635 ± 0.051", "+0.108 vs photo", "3/3"],
    ["Positive control, fusion + synthetic a = 0.3 (3 seeds)", "0.532 ± 0.024", "+0.005 vs photo", "2/3"],
    ["Stacking: photo only", "0.496 ± 0.041", "reference", "—"],
    ["Stacking: photo + raw answers", "0.476 ± 0.038", "-0.020 [-0.044, +0.006]", "2/10"],
    ["Stacking: photo + questionnaire MLP", "0.491 ± 0.031", "-0.005 [-0.020, +0.011]", "4/10"],
    ["Stacking: photo + synthetic a = 0.3", "0.513 ± 0.048", "+0.017 ± 0.036", "6/10"],
    ["Stacking: photo + synthetic a = 0.5", "0.577 ± 0.047", "+0.081 ± 0.046", "10/10"],
]
RO_NAMES = ["Control pozitiv, fuziune + sintetic a = 0,5 (3 seed-uri)", "Control pozitiv, fuziune + sintetic a = 0,3 (3 seed-uri)",
            "Stivuire: doar fotografie", "Stivuire: fotografie + răspunsuri brute", "Stivuire: fotografie + MLP chestionar",
            "Stivuire: fotografie + sintetic a = 0,3", "Stivuire: fotografie + sintetic a = 0,5"]


def ro(s: str) -> str:
    return s.replace(", ", "; ").replace(".", ",").replace("vs photo", "față de fotografie").replace("reference", "referință")


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
        ("Teza_Licenta.docx", "8.7 Este rezultatul nul o eroare de metodă? Control pozitiv și stivuire",
         "Capitolul 9. Concluzii și direcții viitoare", RO,
         [["Model", "Macro-F1", "Diferență", "Seed-uri mai bune"]]
         + [[n] + [ro(x) for x in d[1:]] for n, d in zip(RO_NAMES, DATA)],
         "Tabelul 8.7. Verificările de metodă (test, macro-F1; stivuirea pe zece seed-uri, diferențe pereche față de "
         "combinatorul doar cu fotografia cu interval bootstrap de 95% sau ± abatere standard pentru întrebarea "
         "sintetică)."),
        ("Paper_Skin_Concern.docx", "4.7 Is the null result a method error? Positive control and stacking",
         "5. Discussion", EN, [["Model", "Macro-F1", "Difference", "Seeds better"]] + DATA,
         "Table 6. Method checks (test, macro-F1; stacking over ten seeds, paired differences against the photo-only "
         "combiner with 95% bootstrap interval, or ± standard deviation for the synthetic question).")):
    ed = DocEditor(str(ROOT / "docs" / path))
    if ed.has_heading(head):
        print(path, "already updated")
        continue
    n = {"wang": ed.add_reference(WANG[1], WANG[0]), "wolpert": ed.add_reference(WOLPERT[1], WOLPERT[0])}
    anchor = ed.heading(next_head)
    ed.heading_before(anchor, head, 2)
    for t in paras[:3]:
        ed.body_paragraph_before(anchor, t.format(**n))
    add_table(ed, anchor, rows, cap)
    for t in paras[3:]:
        ed.body_paragraph_before(anchor, t.format(**n))
    try:
        ed.save()
        print(path, "updated")
    except PermissionError:
        print(path, "LOCKED (open in Word) - not updated")
