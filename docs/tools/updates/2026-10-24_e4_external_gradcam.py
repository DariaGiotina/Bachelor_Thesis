"""E4 on external sets (Fitzpatrick17k, DDI, out-of-scope and malignant lesions), app model choice, and
Grad-CAM (Task 4.3): end of thesis 8.11 / paper 4.11, new thesis 8.12 / paper 4.12."""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocEditor  # noqa: E402

REF = {
    "ddi": ("https://doi.org/10.1126/sciadv.abq6147", "R. Daneshjou et al., Disparities in dermatology AI performance on a "
            "diverse, curated clinical image set, Science Advances 8(32), 2022"),
    "gradcam": ("https://arxiv.org/abs/1610.02391", "R. R. Selvaraju et al., Grad-CAM: Visual Explanations from Deep "
                "Networks via Gradient-based Localization, ICCV 2017"),
    "adebayo": ("https://arxiv.org/abs/1810.03292", "J. Adebayo et al., Sanity Checks for Saliency Maps, NeurIPS 2018"),
    "registers": ("https://arxiv.org/abs/2309.16588", "T. Darcet, M. Oquab, J. Mairal, P. Bojanowski, Vision "
                  "Transformers Need Registers, ICLR 2024"),
}

EXT_ROWS = [  # set, model, in-scope accuracy, in-scope abstention I-II / V-VI, out-of-scope abstention ALL (I-II / V-VI), malignant answered
    ["Fitzpatrick17k", "EfficientNet-B0", "42.9", "27.5 / 38.8", "31.6 (29.9 / 36.0)", "-"],
    ["Fitzpatrick17k", "DINOv2 + probe", "53.8", "16.6 / 14.0", "18.6 (19.7 / 15.4)", "-"],
    ["DDI", "EfficientNet-B0", "45.6", "45.9 / 46.2", "45.5 (44.4 / 41.1)", "55.0 (52.7 / 70.0)"],
    ["DDI", "DINOv2 + probe", "25.6", "28.8 / 10.4", "21.4 (25.2 / 16.6)", "79.5 (79.0 / 87.3)"],
]
GC_ROWS = [  # model, rho classifier randomised, rho top randomised, share |rho| < 0.3 (classifier), top-10% share, padding ratio median, cases > 2x
    ["EfficientNet-B0, fine-tuned", "0.10 ± 0.44", "0.02 ± 0.39", "41.7%", "0.32", "0.25", "0.6%"],
    ["DINOv2 + linear probe", "0.02 ± 0.24", "0.02 ± 0.21", "77.5%", "0.39", "0.67", "3.7%"],
]

E4X_RO = [
    "Verificarea externă extinsă. Ambele modele candidate (EfficientNet-B0 și DINOv2 + sondă) au fost aplicate, cu "
    "T și τ din SCIN, pe toate imaginile din Fitzpatrick17k (16.571) și din DDI [{ddi}] (656 de imagini cu diagnostic "
    "confirmat prin biopsie, distribuite echilibrat pe tonuri: 208 FST I-II, 241 III-IV, 207 V-VI; toate fișierele au "
    "fost verificate: complete, lizibile, fără duplicate exacte). Imaginile sunt împărțite în două: în domeniu "
    "(diagnosticul corespunde uneia dintre cele patru categorii) și în afara domeniului (orice alt diagnostic, pe care "
    "modelul nu l-a văzut niciodată; aici răspunsul corect este abținerea). DDI conține doar 178 de imagini în domeniu, "
    "dintre care 172 normal_other (nevi și veruci), deci nu permite un macro-F1 util, dar conține 171 de leziuni maligne "
    "(de exemplu melanom), toate în afara domeniului. Intervalele provin dintr-un bootstrap pe imagini întregi, deoarece "
    "aceleași imagini sunt evaluate de toate cele zece modele.",
    "Rezultatele (Tabelul 8.12) arată o limită importantă a regulii de abținere. Pe imaginile în domeniu din "
    "Fitzpatrick17k, DINOv2 este mult mai precis decât EfficientNet-B0 (53,8% față de 42,9%) și fără diferență între "
    "tonuri. Pe imaginile în afara domeniului însă, încrederea nu separă cazurile necunoscute: DINOv2 se abține la "
    "doar 18,6% dintre ele în Fitzpatrick17k și la 21,4% în DDI, aproape cât pe cele cunoscute, și mai rar pe pielea "
    "închisă (DDI: 25,2% la FST I-II, 16,6% la V-VI). Cel mai grav, DINOv2 dă un răspuns sigur, cu o categorie benignă "
    "(mai ales eczema_dermatitis), pentru 79,5% dintre leziunile maligne din DDI (87,3% la FST V-VI); EfficientNet-B0 "
    "face același lucru pentru 55,0% (70,0% la V-VI). Concluzia este că abținerea bazată pe încredere funcționează în "
    "domeniul de antrenare (secțiunile de mai sus), dar nu poate fi folosită ca filtru de siguranță pentru afecțiuni "
    "grave din afara celor patru categorii.",
    "Decizia pentru aplicație. Modelul livrat este DINOv2 ViT-B/14 cu sonda liniară, cu încrederea calibrată și pragul "
    "τ, ales pentru licența Apache 2.0 (permite publicarea și utilizarea comercială), acuratețea selectivă de 0,676 și "
    "cea mai mică eroare de calibrare după scalare. Din rezultatul extern rezultă două cerințe: aplicația afișează "
    "permanent că nu evaluează leziuni suspecte (alunițe care se schimbă, leziuni care sângerează) și trimite direct la "
    "medic pentru ele, iar înainte de livrare se adaugă un detector separat pentru imagini în afara domeniului (de "
    "exemplu distanța trăsăturilor DINOv2 față de cele din antrenare), evaluat pe aceleași seturi externe și pe "
    "tonuri de piele.",
]
E4X_EN = [
    "Extended external check. Both candidate models (EfficientNet-B0 and DINOv2 + probe) were applied, with their SCIN "
    "T and tau, to every image of Fitzpatrick17k (16,571) and DDI [{ddi}] (656 biopsy-confirmed images, balanced over "
    "tones: 208 FST I-II, 241 III-IV, 207 V-VI; all files were checked: complete, readable, no exact duplicates). The "
    "images are split into in scope (the diagnosis maps to one of our four categories) and out of scope (any other "
    "diagnosis, which the model never saw; here the right answer is to abstain). DDI has only 178 in-scope images, 172 "
    "of them normal_other (nevi and warts), so it gives no useful macro-F1, but it contains 171 malignant lesions (for "
    "example melanoma), all out of scope. Intervals come from a bootstrap over whole images, since the same images are "
    "scored by all ten models.",
    "The results (Table 13) show an important limit of the abstention rule. On the in-scope Fitzpatrick17k images "
    "DINOv2 is far more accurate than EfficientNet-B0 (53.8% against 42.9%), with no gap between tones. On out-of-scope "
    "images, however, confidence does not separate the unknown cases: DINOv2 abstains on only 18.6% of them in "
    "Fitzpatrick17k and 21.4% in DDI, about as often as on known ones, and less often on dark skin (DDI: 25.2% for FST "
    "I-II, 16.6% for V-VI). Most seriously, DINOv2 gives a confident answer with a benign category (mostly "
    "eczema_dermatitis) for 79.5% of the DDI malignant lesions (87.3% for FST V-VI); EfficientNet-B0 does so for 55.0% "
    "(70.0% for V-VI). Confidence-based abstention therefore works inside the training domain (sections above), but it "
    "cannot serve as a safety filter for serious conditions outside the four categories.",
    "Decision for the app. The shipped model is DINOv2 ViT-B/14 with the linear probe, calibrated confidence and the "
    "threshold tau, chosen for its Apache 2.0 licence (publication and commercial use allowed), its selective accuracy "
    "of 0.676 and the lowest calibration error after scaling. The external result adds two requirements: the app "
    "always states that it does not assess suspicious lesions (changing moles, bleeding lesions) and sends them "
    "straight to a doctor, and before release a separate out-of-scope detector is added (for example the distance of "
    "the DINOv2 features to the training features), evaluated on the same external sets and by skin tone.",
]
GC_RO = [
    "Grad-CAM [{gradcam}] explică o predicție printr-o hartă de căldură: activările unui strat al rețelei sunt ponderate "
    "cu gradientul scorului clasei prezise, iar partea pozitivă arată regiunile imaginii care au crescut acel scor. "
    "Pentru EfficientNet-B0 se folosește ultimul strat convoluțional; pentru DINOv2 (Vision Transformer), intrarea "
    "ultimului bloc, cu token-urile de patch rearanjate în grila lor (37 × 37 la 518 pixeli). Scriptul "
    "`ml/run_gradcam.py` calculează harta clasei prezise pentru toate cazurile de test din cele zece seed-uri (2.708 pe "
    "model). Exemplele vizuale (cazuri corecte, greșite și cu abținere, pe grupe eFST) rămân locale, deoarece conțin "
    "fotografii SCIN care nu sunt redistribuite; în lucrare se raportează doar măsuri numerice.",
    "Verificarea de sănătate prin randomizarea modelului [{adebayo}]: o hartă care rămâne la fel când ponderile pe care "
    "ar trebui să le explice sunt distruse nu explică nimic. Se compară harta modelului antrenat cu harta obținută după "
    "înlocuirea cu zgomot a ponderilor clasificatorului și apoi și a ultimelor blocuri ale encoderului, prin corelația "
    "Spearman (corelația rangurilor, între -1 și 1; 0 = fără legătură). Se mai măsoară cât de concentrată este harta "
    "(proporția masei în cei mai fierbinți 10% pixeli) și raportul de bordură: masa hărții pe pixel în zona neagră de "
    "completare a imaginii (letterbox), raportată la media pe imagine (1 = nicio preferință; mult peste 1 = modelul se "
    "uită la bordură, o scurtătură).",
    "Rezultatele (Tabelul 8.13): ambele modele trec verificarea în medie (corelații 0,02-0,10 după randomizare), dar "
    "DINOv2 o trece mai consecvent: la 77,5% dintre cazuri corelația după randomizarea clasificatorului este sub 0,3 în "
    "valoare absolută, față de 41,7% la EfficientNet-B0, ale cărui hărți depind mult de activările generale ale ultimului "
    "strat. Hărțile DINOv2 sunt mai concentrate (0,39 față de 0,32), dar acordă mai multă atenție bordurii (mediană 0,67 "
    "față de 0,25; 3,7% dintre cazuri peste dublul mediei, față de 0,6%), mai ales la predicțiile acne și normal_other. "
    "Este un efect cunoscut al Vision Transformer-ilor de tip DINOv2 fără token-uri de registru, care stochează "
    "informație globală în patch-uri fără conținut [{registers}]. Concentrarea hărților nu diferă între tonurile de "
    "piele (0,36-0,41 la toate grupele eFST, pentru cazuri corecte, greșite și cu abținere). Pentru aplicație, harta "
    "DINOv2 este afișată doar ca indicație generală, iar ca îmbunătățire se propune completarea prin reflexie în locul "
    "bordurii negre sau varianta DINOv2 cu registre.",
]
GC_EN = [
    "Grad-CAM [{gradcam}] explains a prediction with a heatmap: the activations of one layer are weighted by the "
    "gradient of the predicted class score, and the positive part shows the image regions that raised that score. "
    "EfficientNet-B0 uses its last convolutional layer; DINOv2 (a Vision Transformer) uses the input of its last block, "
    "with the patch tokens reshaped into their grid (37 x 37 at 518 pixels). The script `ml/run_gradcam.py` computes "
    "the map of the predicted class for every test case of the ten seeds (2,708 per model). Visual examples (correct, "
    "wrong and abstained cases per eFST group) stay local because they show SCIN photos, which are not redistributed; "
    "only numerical measures are reported.",
    "The model-randomization sanity check [{adebayo}]: a map that stays the same when the weights it should explain "
    "are destroyed explains nothing. The trained model's map is compared with the map after the classifier weights, "
    "and then also the last encoder blocks, are replaced by noise, using the Spearman correlation (rank correlation "
    "between -1 and 1; 0 = unrelated). Also measured are how focused the map is (share of its mass in the hottest 10% "
    "of pixels) and the padding ratio: map mass per pixel on the black letterbox padding relative to the image average "
    "(1 = no preference; well above 1 = the model looks at the padding, a shortcut).",
    "The results (Table 14): both models pass the check on average (correlations 0.02-0.10 after randomization), but "
    "DINOv2 passes it more consistently: in 77.5% of cases the correlation after randomizing the classifier is below "
    "0.3 in absolute value, against 41.7% for EfficientNet-B0, whose maps depend strongly on the generic activations "
    "of its last layer. DINOv2 maps are more focused (0.39 against 0.32) but give more weight to the padding (median "
    "0.67 against 0.25; 3.7% of cases above twice the average, against 0.6%), especially for acne and normal_other "
    "predictions. This is a known effect of DINOv2-type Vision Transformers without register tokens, which store "
    "global information in content-free patches [{registers}]. Map focus does not differ between skin tones "
    "(0.36-0.41 for every eFST group, for correct, wrong and abstained cases). In the app the DINOv2 map is shown only "
    "as a rough indication; reflection padding instead of black borders, or the DINOv2 variant with registers, is "
    "proposed as an improvement.",
]


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


def ro(s: str) -> str:
    return s.replace(".", ",")


DOCS = {
    "Teza_Licenta.docx": dict(
        next_head="Capitolul 9. Concluzii și direcții viitoare", e4x=E4X_RO, gc=GC_RO,
        gc_head="8.12 Explicabilitate: Grad-CAM și verificarea de sănătate",
        t_ext=[["Set", "Model", "Acuratețe în domeniu (%)", "Abținere în domeniu FST I-II / V-VI (%)",
                "Abținere în afara domeniului: total (I-II / V-VI) (%)", "Leziuni maligne cu răspuns sigur (%)"]]
        + [[r[0], r[1].replace("probe", "sondă")] + [ro(x) for x in r[2:]] for r in EXT_ROWS],
        t_ext_cap="Tabelul 8.12. Modelele candidate pe seturile externe, zero-shot, cu T și τ din SCIN (medii pe zece "
                  "modele; în afara domeniului și pentru leziunile maligne abținerea este răspunsul corect).",
        t_gc=[["Model", "ρ, clasificator randomizat", "ρ, clasificator + vârful encoderului", "Cazuri cu |ρ| < 0,3",
               "Masa în top 10% pixeli", "Raport de bordură (mediană)", "Cazuri cu raport > 2"]]
        + [[r[0].replace("fine-tuned", "ajustat fin").replace("linear probe", "sondă liniară")] + [ro(x) for x in r[1:]]
           for r in GC_ROWS],
        t_gc_cap="Tabelul 8.13. Grad-CAM pe testul SCIN (2.708 cazuri pe model, zece seed-uri; ρ = corelația Spearman "
                 "cu harta modelului antrenat, medie ± abatere standard)."),
    "Paper_Skin_Concern.docx": dict(
        next_head="5. Discussion", e4x=E4X_EN, gc=GC_EN, gc_head="4.12 Explainability: Grad-CAM and sanity check",
        t_ext=[["Set", "Model", "In-scope accuracy (%)", "In-scope abstention FST I-II / V-VI (%)",
                "Out-of-scope abstention: all (I-II / V-VI) (%)", "Malignant lesions answered confidently (%)"]]
        + EXT_ROWS,
        t_ext_cap="Table 13. Candidate models on the external sets, zero-shot, with the SCIN T and tau (means over ten "
                  "models; out of scope and for malignant lesions, abstaining is the right answer).",
        t_gc=[["Model", "rho, classifier randomised", "rho, classifier + top of encoder", "Cases with |rho| < 0.3",
               "Mass in top 10% pixels", "Padding ratio (median)", "Cases with ratio > 2"]] + GC_ROWS,
        t_gc_cap="Table 14. Grad-CAM on the SCIN test split (2,708 cases per model, ten seeds; rho = Spearman "
                 "correlation with the trained model's map, mean ± standard deviation)."),
}

for path, d in DOCS.items():
    ed = DocEditor(str(ROOT / "docs" / path))
    if ed.has_heading(d["gc_head"]):
        print(path, "already updated")
        continue
    n = {k: ed.add_reference(v[1], v[0]) for k, v in REF.items()}
    anchor = ed.heading(d["next_head"])
    ed.body_paragraph_before(anchor, d["e4x"][0].format(**n))
    add_table(ed, anchor, d["t_ext"], d["t_ext_cap"])
    for t in d["e4x"][1:]:
        ed.body_paragraph_before(anchor, t.format(**n))
    ed.heading_before(anchor, d["gc_head"], 2)
    for t in d["gc"][:2]:
        ed.body_paragraph_before(anchor, t.format(**n))
    add_table(ed, anchor, d["t_gc"], d["t_gc_cap"])
    ed.body_paragraph_before(anchor, d["gc"][2].format(**n))
    try:
        ed.save()
        print(path, "updated")
    except PermissionError:
        print(path, "LOCKED (open in Word) - not updated")
