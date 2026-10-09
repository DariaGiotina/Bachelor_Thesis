"""Ten-seed E1 results with skin-tone and category analysis: thesis 8.4 / paper 4.4 (sections 8.2-8.3 / 4.2-4.3 become preliminary)."""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocEditor  # noqa: E402

HOLM = ("https://www.jstor.org/stable/4615733",
        "S. Holm, A Simple Sequentially Rejective Multiple Test Procedure, Scandinavian Journal of Statistics 6(2), 1979")
WILC = ("https://doi.org/10.2307/3001968", "F. Wilcoxon, Individual Comparisons by Ranking Methods, Biometrics "
        "Bulletin 1(6), 1945")

RO = [
    "Rezultatele din secțiunile 8.2 și 8.3 folosesc primele cinci seed-uri și sunt preliminare. Pentru a strânge "
    "intervalele de încredere, s-au creat încă cinci variante de împărțire (seed-urile 5–9; împărțirile 0–4 au rămas "
    "identice) și toate brațele au fost reantrenate pe ele. Planul de analiză a fost stabilit înainte de a vedea noile "
    "rezultate: aceleași brațe, aceleași metrici, diferențe pereche față de modelul doar cu imagine, iar pe grupuri de "
    "ton și pe categorii, valori p corectate Holm [{holm}]. Corecția Holm este necesară deoarece se fac multe teste "
    "deodată (6 grupuri de ton și 4 categorii pentru fiecare model): cu 10 teste, cel puțin un rezultat „semnificativ” "
    "poate apărea din întâmplare, iar corecția crește pragul astfel încât probabilitatea unei astfel de alarme false în "
    "întreaga familie de teste să rămână sub 5%. Testul Wilcoxon [{wilc}] compară diferențele pe seed-uri fără să "
    "presupună o distribuție normală. Rezultatele complete sunt în `ml/results/e1/` (toate cele zece seed-uri), iar "
    "jumătățile `seeds0-4` și `seeds5-9` sunt raportate separat ca verificare de replicare.",
    "Pe zece seed-uri (Tabelul 8.4), modelul doar cu imagine obține macro-F1 0,519 ± 0,040, iar niciuna dintre "
    "variantele care folosesc chestionarul nu îl depășește: concatenare −0,005 [IÎ 95% −0,024; +0,014], mai bună la "
    "6 din 10 seed-uri; FiLM +0,000 [−0,023; +0,023], 5/10; concatenare fără dropout −0,014 [−0,035; +0,006]; ansamblu "
    "−0,021 [−0,047; +0,003]. Fuziunea cu poartă este chiar mai slabă: −0,030 [−0,053; −0,007], mai bună doar la 2 din "
    "10 seed-uri (Wilcoxon p = 0,037). Avantajul mic al variantei FiLM pe primele cinci seed-uri (+0,008) a dispărut, "
    "ceea ce arată de ce cinci seed-uri nu sunt suficiente. Intervalele mai înguste permit o concluzie mai fermă: cu "
    "95% încredere, un eventual câștig adus de chestionar în această configurație este mai mic de aproximativ 0,02 "
    "macro-F1 (limita superioară a intervalului pentru FiLM este +0,023, pentru concatenare +0,014).",
    "Analiza pe grupuri arată același lucru și pentru întrebarea „pentru cine?”. Niciuna dintre variantele de fuziune "
    "nu îmbunătățește semnificativ vreun grup de ton (eFST I–II, III–IV, V–VI; eMST 1–3, 4–6, 7–10) sau vreo "
    "categorie după corecția Holm; singurul efect semnificativ al fuziunii este negativ: varianta cu poartă scade "
    "macro-F1 pe eFST III–IV cu 0,073 (p Holm = 0,028). Pe primele cinci seed-uri, FiLM părea mai bună pe grupul "
    "eMST 4–6 (+0,088, la toate cele 5 seed-uri); acest indiciu a fost notat înainte de rularea seed-urilor 5–9 și nu "
    "s-a replicat (−0,013, mai bună la un singur seed din cinci), deci era zgomot. Modelul doar cu imagine are cel mai "
    "slab rezultat pe eMST 4–6 (0,457 ± 0,069, circa 72 de cazuri pe seed) și pe eFST V–VI (0,496 ± 0,140, circa 23 de "
    "cazuri), iar pe categorii acneea rămâne cea mai dificilă (F1 0,320 ± 0,064). Un detaliu util pentru discuție: "
    "diferența dintre chestionar și imagine este cea mai mică tocmai pe grupurile mai închise la culoare (eFST V–VI "
    "−0,070, eMST 4–6 −0,050, ambele nesemnificative, față de −0,12 ... −0,20 pe celelalte grupuri), ceea ce sugerează "
    "că fotografia pierde din avantaj pe pielea mai închisă, dar modelele cu fuziune nu reușesc să compenseze cu "
    "chestionarul. Grupurile mici (eMST 7–10 are 11 cazuri pe seed, redness_rosacea 6) au intervale foarte largi și nu "
    "permit concluzii.",
]
EN = [
    "The results in Sections 4.2 and 4.3 use the first five seeds and are preliminary. To narrow the confidence "
    "intervals, five more split variants were created (seeds 5-9; splits 0-4 stayed identical) and every arm was "
    "retrained on them. The analysis plan was fixed before the new results were seen: the same arms and metrics, paired "
    "differences against the photo-only model, and Holm-corrected p-values [{holm}] for tone groups and categories. The "
    "Holm correction is needed because many tests are run at once (6 tone groups and 4 categories per model): with 10 "
    "tests, at least one 'significant' result can appear by chance, and the correction raises the threshold so that the "
    "probability of any such false alarm in the whole family stays below 5%. The Wilcoxon signed-rank test [{wilc}] "
    "compares the per-seed differences without assuming a normal distribution. Full results are in `ml/results/e1/` "
    "(all ten seeds), and the halves `seeds0-4` and `seeds5-9` are reported separately as a replication check.",
    "Over ten seeds (Table 4), the photo-only model reaches a macro-F1 of 0.519 ± 0.040, and none of the variants that "
    "use the questionnaire beats it: concatenation −0.005 [95% CI −0.024, +0.014], better in 6 of 10 seeds; FiLM +0.000 "
    "[−0.023, +0.023], 5/10; concatenation without dropout −0.014 [−0.035, +0.006]; ensemble −0.021 [−0.047, +0.003]. "
    "Gated fusion is even worse: −0.030 [−0.053, −0.007], better in only 2 of 10 seeds (Wilcoxon p = 0.037). The small "
    "lead of FiLM over the first five seeds (+0.008) disappeared, which shows why five seeds are not enough. The "
    "narrower intervals allow a firmer conclusion: with 95% confidence, any gain from the questionnaire in this "
    "configuration is smaller than about 0.02 macro-F1 (the upper end of the interval is +0.023 for FiLM and +0.014 "
    "for concatenation).",
    "The group analysis gives the same answer to the question 'for whom?'. No fusion variant significantly improves any "
    "tone group (eFST I-II, III-IV, V-VI; eMST 1-3, 4-6, 7-10) or any category after the Holm correction; the only "
    "significant effect of fusion is negative: the gated variant lowers macro-F1 on eFST III-IV by 0.073 (Holm "
    "p = 0.028). Over the first five seeds, FiLM seemed better on eMST 4-6 (+0.088, in all 5 seeds); this hint was "
    "recorded before seeds 5-9 were run and did not replicate (−0.013, better in only one seed of five), so it was "
    "noise. The photo-only model is weakest on eMST 4-6 (0.457 ± 0.069, about 72 cases per seed) and on eFST V-VI "
    "(0.496 ± 0.140, about 23 cases), and acne remains the hardest category (F1 0.320 ± 0.064). One detail matters for "
    "the discussion: the gap between the questionnaire and the photo is smallest precisely on the darker groups (eFST "
    "V-VI −0.070, eMST 4-6 −0.050, both not significant, versus −0.12 to −0.20 on the other groups), which suggests that "
    "the photo loses part of its advantage on darker skin, but the fusion models do not manage to compensate with the "
    "questionnaire. Small groups (eMST 7-10 has 11 cases per seed, redness_rosacea 6) have very wide intervals and do "
    "not support conclusions.",
]
HEAD_RO = ["Model", "Macro-F1 (10 seed-uri)", "Diferență față de imagine [IÎ 95%]", "Seed-uri mai bune",
           "Macro-F1, răspunsuri ascunse"]
HEAD_EN = ["Model", "Macro-F1 (10 seeds)", "Difference vs photo [95% CI]", "Seeds better", "Macro-F1, answers hidden"]
DATA = [
    ("Doar imagine", "Photo only", "0.519 ± 0.040", "-", "-", "-"),
    ("Doar chestionar", "Questionnaire only", "0.381 ± 0.050", "-0.138 [-0.173, -0.102]", "0/10", "0.138"),
    ("Fuziune concat", "Fusion concat", "0.514 ± 0.040", "-0.005 [-0.024, +0.014]", "6/10", "0.505"),
    ("Fuziune cu poartă", "Fusion gated", "0.490 ± 0.041", "-0.030 [-0.053, -0.007]", "2/10", "0.491"),
    ("Fuziune FiLM", "Fusion FiLM", "0.519 ± 0.044", "+0.000 [-0.023, +0.023]", "5/10", "0.513"),
    ("Concat fără dropout", "Concat, no dropout", "0.505 ± 0.036", "-0.014 [-0.035, +0.006]", "3/10", "0.504"),
    ("Ansamblu imagine × chestionar", "Ensemble photo × questionnaire", "0.498 ± 0.052", "-0.021 [-0.047, +0.003]",
     "3/10", "0.496"),
]


def ro(s: str) -> str:
    return s.replace(".", ",").replace(", ", "; ") if any(ch.isdigit() for ch in s) and "/" not in s else s


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
        ("Teza_Licenta.docx", "8.4 Rezultatele finale pe zece seed-uri, pe tonuri de piele și pe categorii",
         "Capitolul 9. Concluzii și direcții viitoare", RO,
         [HEAD_RO] + [[d[0], ro(d[2]), ro(d[3]), d[4], ro(d[5])] for d in DATA],
         "Tabelul 8.4. Toate brațele E1 pe zece seed-uri (EfficientNet-B0, pierdere ponderată; medie ± abatere "
         "standard; diferențe pereche pe aceleași cazuri, interval bootstrap stratificat pe seed)."),
        ("Paper_Skin_Concern.docx", "4.4 Final results over ten seeds, by skin tone and by category", "5. Discussion",
         EN, [HEAD_EN] + [[d[1], d[2], d[3], d[4], d[5]] for d in DATA],
         "Table 4. All E1 arms over ten seeds (EfficientNet-B0, weighted loss; mean ± standard deviation; paired "
         "differences on the same cases, seed-stratified bootstrap interval).")):
    ed = DocEditor(str(ROOT / "docs" / path))
    if ed.has_heading(head):
        print(path, "already updated")
        continue
    n = {"holm": ed.add_reference(HOLM[1], HOLM[0]), "wilc": ed.add_reference(WILC[1], WILC[0])}
    anchor = ed.heading(next_head)
    ed.heading_before(anchor, head, 2)
    ed.body_paragraph_before(anchor, paras[0].format(**n))
    ed.body_paragraph_before(anchor, paras[1])
    add_table(ed, anchor, rows, cap)
    ed.body_paragraph_before(anchor, paras[2])
    try:
        ed.save()
        print(path, "updated")
    except PermissionError:
        print(path, "LOCKED (open in Word) - not updated")
