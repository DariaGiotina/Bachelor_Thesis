"""New thesis 5.11 / paper 3.10: external test sets (DDI, Fitzpatrick17k) and the foundation-model linear probe."""
import copy
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx.oxml.ns import qn  # noqa: E402
from docx_tools import DocEditor  # noqa: E402

REFS = {
    "ddi": ("https://doi.org/10.1126/sciadv.abq6147",
            "R. Daneshjou et al., Disparities in dermatology AI performance on a diverse, curated clinical image set, "
            "Science Advances 8(32), 2022"),
    "f17k": ("https://arxiv.org/abs/2104.09957",
             "M. Groh et al., Evaluating Deep Neural Networks Trained on Clinical Images in Dermatology with the "
             "Fitzpatrick 17k Dataset, CVPR Workshops 2021"),
    "probe": ("https://arxiv.org/abs/1610.01644",
              "G. Alain, Y. Bengio, Understanding intermediate layers using linear classifier probes, arXiv 2016"),
    "clip": ("https://arxiv.org/abs/2103.00020",
             "A. Radford et al., Learning Transferable Visual Models From Natural Language Supervision, ICML 2021"),
    "panderm": ("https://www.nature.com/articles/s41591-025-03747-y",
                "S. Yan et al., A multimodal vision foundation model for clinical dermatology (PanDerm), "
                "Nature Medicine 2025"),
    "derm1m": ("https://arxiv.org/abs/2503.14911",
               "S. Yan et al., Derm1M: A Million-scale Vision-Language Dataset Aligned with Clinical Ontology "
               "Knowledge for Dermatology (DermLIP), ICCV 2025"),
}

T_HEAD, P_HEAD = "5.11 Evaluarea externă și sonda liniară", "3.10 External test sets and linear probe"
RO = [
    "Pentru a verifica dacă modelul doar cu imagine antrenat pe SCIN funcționează și pe fotografii provenite din alte "
    "surse, acesta este testat fără nicio reantrenare (evaluare externă, zero-shot) pe două seturi publice: DDI (Diverse "
    "Dermatology Images) [{ddi}], 656 de imagini clinice confirmate prin biopsie (examinarea la microscop a unei mostre de "
    "țesut), grupate pe tonuri Fitzpatrick I–II, III–IV și V–VI, și Fitzpatrick17k [{f17k}], 16.577 de imagini din "
    "atlase dermatologice online, cu 114 diagnostice și tipul Fitzpatrick 1–6. Niciunul nu are chestionar, deci se "
    "testează doar modelul cu imagine. Diferența dintre sursa de antrenare și cea de testare (alt aparat, altă "
    "încadrare, alte boli) se numește schimbare de domeniu (domain shift); scăderea performanței pe aceste seturi arată "
    "cât de mult depinde modelul de particularitățile SCIN.",
    "Diagnosticele externe sunt aduse la cele patru categorii țintă cu același fișier `label_map.yaml`, după "
    "normalizare (litere mici, cratima citită ca spațiu), plus o listă scurtă de sinonime pe set de date (de exemplu "
    "„acne vulgaris” → acne, „rhinophyma” → redness_rosacea). Fiecare rând primește un statut scris într-un raport: "
    "păstrat, categorie nețintă (de exemplu cancerele, care sunt `excluded`), nemapat (diagnostic necunoscut, niciodată "
    "ghicit), etichetă greșită conform controlului de calitate al Fitzpatrick17k sau imagine lipsă; doar rândurile "
    "păstrate sunt evaluate. În Fitzpatrick17k, 4.012 imagini corespund categoriilor țintă (normal_other 1.892, "
    "eczema_dermatitis 1.009, acne 857, redness_rosacea 254), dar normal_other este dominată aici de psoriazis, deci "
    "compoziția categoriei diferă de SCIN. O limitare practică: majoritatea adreselor de imagini din Fitzpatrick17k "
    "(atlasul DermaAmin) nu mai funcționează, iar setul complet se obține de la autori prin formular. Imaginile nu sunt "
    "redistribuite (licența CC BY-NC-SA 3.0 pentru Fitzpatrick17k; condițiile Stanford AIMI pentru DDI). Tonul DDI 12 / "
    "34 / 56 este tratat ca grupul eFST I–II / III–IV / V–VI, iar predicțiile tuturor celor cinci modele (câte unul pe "
    "seed) sunt evaluate cu același protocol ca pe SCIN.",
    "Ca bază de comparație pentru experimentul E5 se folosește o sondă liniară (linear probe) [{probe}]. Un model "
    "fundament (foundation model) este o rețea mare, preantrenată pe foarte multe imagini, ale cărei reprezentări pot fi "
    "refolosite pentru multe sarcini; în dermatologie, exemple sunt PanDerm [{panderm}] și DermLIP [{derm1m}]. Rețeaua "
    "rămâne înghețată (ponderile ei nu se schimbă): pentru fiecare caz SCIN se calculează o singură dată vectorul de "
    "trăsături (features), adică lista de numere prin care rețeaua descrie imaginea, iar peste aceste trăsături se "
    "antrenează doar un strat liniar, echivalent cu o regresie logistică multinomială. Trăsăturile sunt standardizate "
    "(se scade media și se împarte la abaterea standard, calculate doar pe setul de antrenare), pierderea este "
    "entropia încrucișată ponderată pe clase, iar o penalizare L2 (suma pătratelor ponderilor, înmulțită cu o constantă) "
    "împiedică ponderile să devină prea mari; constanta este aleasă pe validare dintre 0 și 100. Evaluarea prin sondă "
    "liniară este metoda standard de comparare a reprezentărilor [{clip}]: dacă o sondă simplă peste un model fundament "
    "egalează rețeaua reantrenată complet, avantajul vine din reprezentare, nu din antrenare. Scriptul "
    "`ml/foundation_probe.py` acceptă orice model timm, OpenCLIP sau Hugging Face, astfel încât ponderile PanDerm și "
    "DermLIP pot fi folosite fără modificarea codului.",
]
EN = [
    "To check whether the SCIN-trained photo-only model also works on photos from other sources, it is tested without "
    "any retraining (external, zero-shot evaluation) on two public sets: DDI (Diverse Dermatology Images) [{ddi}], 656 "
    "clinical images confirmed by biopsy (microscopic examination of a tissue sample), grouped into Fitzpatrick I-II, "
    "III-IV and V-VI, and Fitzpatrick17k [{f17k}], 16,577 images from online dermatology atlases with 114 diagnoses and "
    "Fitzpatrick type 1-6. Neither has a questionnaire, so only the photo model is tested. The difference between the "
    "training and test sources (other cameras, framing and diseases) is called domain shift; the drop in performance on "
    "these sets shows how much the model depends on the particulars of SCIN.",
    "External diagnoses are mapped to the four target categories with the same `label_map.yaml`, after normalisation "
    "(lower case, hyphen read as a space), plus a short per-dataset list of synonyms (e.g. 'acne vulgaris' -> acne, "
    "'rhinophyma' -> redness_rosacea). Every row gets a status written to a report: kept, non-target category (e.g. "
    "cancers, which are `excluded`), unmapped (unknown diagnosis, never guessed), wrong label according to the "
    "Fitzpatrick17k quality check, or missing image; only kept rows are evaluated. In Fitzpatrick17k, 4,012 images match "
    "the target categories (normal_other 1,892, eczema_dermatitis 1,009, acne 857, redness_rosacea 254), but here "
    "normal_other is dominated by psoriasis, so the category's composition differs from SCIN. A practical limitation: "
    "most Fitzpatrick17k image URLs (the DermaAmin atlas) no longer work, and the full set is obtained from the authors "
    "through a request form. Images are not redistributed (CC BY-NC-SA 3.0 for Fitzpatrick17k; Stanford AIMI terms for "
    "DDI). DDI tones 12 / 34 / 56 are treated as eFST groups I-II / III-IV / V-VI, and the predictions of all five models "
    "(one per seed) are evaluated with the same protocol as on SCIN.",
    "As the baseline for experiment E5 we use a linear probe [{probe}]. A foundation model is a large network pretrained "
    "on very many images whose representations can be reused for many tasks; in dermatology, examples are PanDerm "
    "[{panderm}] and DermLIP [{derm1m}]. The network stays frozen (its weights do not change): for every SCIN case its "
    "feature vector, the list of numbers by which the network describes the image, is computed once, and only a linear "
    "layer is trained on top, which is equivalent to multinomial logistic regression. Features are standardised "
    "(subtracting the mean and dividing by the standard deviation, both computed on the training set only), the loss is "
    "class-weighted cross-entropy, and an L2 penalty (the sum of squared weights times a constant) keeps the weights "
    "from growing too large; the constant is chosen on validation from 0 to 100. Linear-probe evaluation is the standard "
    "way to compare representations [{clip}]: if a simple probe on a foundation model matches the fully fine-tuned "
    "network, the advantage comes from the representation, not the training. `ml/foundation_probe.py` accepts any timm, "
    "OpenCLIP or Hugging Face model, so PanDerm and DermLIP weights can be used without code changes.",
]

for path, head, next_head, toc_page, paras in (
        ("Teza_Licenta.docx", T_HEAD, "Capitolul 6. Implementare", "13", RO),
        ("Paper_Skin_Concern.docx", P_HEAD, "4. Results", None, EN)):
    ed = DocEditor(str(ROOT / "docs" / path))
    if ed.has_heading(head):
        print(path, "already updated")
        continue
    n = {k: ed.add_reference(t, u) for k, (u, t) in REFS.items()}
    anchor = ed.heading(next_head)
    ed.heading_before(anchor, head, 2)
    for text in paras:
        ed.body_paragraph_before(anchor, text.format(**n))
    toc, prev = ed.toc_entries(next_head), ed.toc_entries("5.10 Protocolul de evaluare")
    if toc and prev and toc_page:  # copy the level-2 entry's format, insert before the chapter 6 entry
        new = copy.deepcopy(prev[0]._p)
        toc[0]._p.addprevious(new)
        ts = new.findall(".//" + qn("w:t"))
        ts[0].text, ts[-1].text = head, toc_page
    try:
        ed.save()
        print(path, "updated")
    except PermissionError:
        print(path, "LOCKED (open in Word) - not updated")
