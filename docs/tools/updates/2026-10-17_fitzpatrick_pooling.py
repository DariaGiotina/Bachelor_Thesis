"""Full Fitzpatrick17k image set: complete zero-shot test and the pooled-training experiment E7.

New thesis 8.8 / paper 4.8.
"""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocEditor  # noqa: E402

F17K = ("https://arxiv.org/abs/2104.09957",
        "M. Groh et al., Evaluating Deep Neural Networks Trained on Clinical Images in Dermatology with the "
        "Fitzpatrick 17k Dataset, CVPR Workshops 2021")
DUPS = ("https://doi.org/10.1038/s41597-025-04382-5",
        "K. Abhishek, A. Jain, G. Hamarneh, Investigating the Quality of DermaMNIST and Fitzpatrick17k Dermatological "
        "Image Datasets, Scientific Data 12, 196, 2025")

RO = [
    "Setul complet de imagini Fitzpatrick17k [{f17k}] (16.577 de fișiere) a fost primit de la autori, cu obligația de a "
    "fi șters după încheierea cercetării. Cu el, toate cele 4.012 imagini care corespund categoriilor țintă pot fi "
    "folosite (înainte doar 619 se mai puteau descărca). Imaginile nu sunt redistribuite și nu apar în aplicație, în "
    "depozitul de cod sau în lucrare; se raportează doar valori agregate. Au fost făcute două lucruri: testul extern "
    "complet al modelului SCIN și un experiment nou, E7, care verifică dacă imaginile suplimentare fac modelul mai precis.",
    "Testul extern complet (zero-shot, adică fără nicio reantrenare). Cele zece modele doar cu imagine din E1 (câte unul "
    "pe seed) obțin pe cele 4.012 imagini un macro-F1 de 0,393 ± 0,016, față de 0,519 pe testul SCIN. Scăderea arată "
    "schimbarea de domeniu: fotografiile clinice din atlase diferă de fotografiile făcute cu telefonul în SCIN, iar "
    "categoria normal_other este dominată aici de psoriazis. Performanța scade odată cu tonul pielii: macro-F1 0,412 "
    "pentru eFST I–II, 0,371 pentru III–IV și 0,312 pentru V–VI. Pe categorii, redness_rosacea este cea mai slabă "
    "(F1 0,237).",
    "Duplicate și fotografii ale aceluiași pacient. Fitzpatrick17k conține multe aproape-duplicate [{dups}]: aceeași "
    "fotografie reîncărcată, redimensionată, oglindită sau decupată, și mai multe fotografii ale aceluiași pacient. Dacă "
    "una ajunge în antrenare și alta în test, scorul de test este prea mare (scurgere de date, data leakage). Două "
    "verificări leagă imaginile (`ml/splits/make_fitzpatrick_splits.py`). (a) Hash-ul de diferență (dHash) pe 256 de biți: "
    "imaginea este transformată în tonuri de gri și micșorată la 17 × 16 pixeli, iar fiecare bit spune dacă un pixel "
    "este mai luminos decât vecinul din dreapta. Distanța Hamming (numărul de biți diferiți, 0–256) măsoară cât de "
    "diferite sunt două hash-uri; două imagini sunt legate dacă distanța este cel mult 20. (b) Similaritatea cosinus "
    "(între -1 și 1; 1 înseamnă aceeași direcție) a trăsăturilor ImageNet ale unei rețele EfficientNet-B0 fără "
    "antrenare pe piele; două imagini sunt legate dacă similaritatea este cel puțin 0,88. Pragul a fost ales prin "
    "inspecția vizuală a unor perechi: peste 0,88 aproape toate perechile arătau același pacient sau aceeași leziune, "
    "sub 0,87 apăreau des fotografii fără legătură. Imaginile legate formează grupuri (prin union-find, o structură care "
    "unește grupurile pe măsură ce apar legături): 588 de perechi, 903 imagini în grupuri de cel puțin două. Pentru "
    "fiecare seed, `StratifiedGroupKFold` (împărțire în cinci părți care păstrează grupurile întregi și proporția "
    "categoriilor) pune circa 20% din grupuri în setul de test Fitzpatrick17k (803 imagini), restul de 3.209 imagini "
    "putând fi folosite la antrenare.",
    "Experimentul E7 (`ml/run_fitz_pooling.py`) compară modelul doar cu imagine din E1 cu două moduri de a folosi "
    "imaginile suplimentare, cu aceeași rețea (EfficientNet-B0), aceeași antrenare în etape și aceleași zece seed-uri: "
    "(1) reunirea datelor (data pooling): antrenarea pe SCIN și pe partea de antrenare Fitzpatrick17k împreună, cu "
    "ponderi de clasă calculate pe setul reunit; (2) transfer secvențial: antrenarea întâi doar pe Fitzpatrick17k, apoi "
    "ajustarea fină (fine-tuning, continuarea antrenării cu o rată de învățare mică) pe SCIN. Oprirea timpurie folosește "
    "mereu validarea SCIN, deoarece ținta aplicației sunt fotografiile de telefon. Fiecare model este testat pe testul "
    "SCIN (pereche cu E1, pe aceleași cazuri) și pe setul de test Fitzpatrick17k al seed-ului, pe care nu l-a văzut. "
    "Experimentul este doar de cercetare: modelul livrat în aplicație rămâne antrenat numai pe SCIN.",
    "Rezultatele (Tabelul 8.8) răspund negativ la întrebarea dacă imaginile suplimentare ajută ținta aplicației. Pe "
    "testul SCIN, reunirea datelor scade macro-F1 cu 0,035 [-0,071; -0,002] (mai bună doar în 2 din 10 seed-uri; "
    "t-test pereche p = 0,016), iar acuratețea echilibrată (media recall-ului pe categorii) scade de la 0,610 la 0,499. "
    "Transferul secvențial scade macro-F1 cu 0,024 [-0,049; +0,001] (3/10 seed-uri). Pe categorii, reunirea crește F1 "
    "pentru eczema_dermatitis (+0,042) dar îl scade pentru redness_rosacea (-0,107) și acne (-0,057). Pe setul "
    "Fitzpatrick17k, în schimb, reunirea crește macro-F1 de la 0,410 (zero-shot) la 0,626 (+0,216, 10/10 seed-uri), iar "
    "diferența dintre tonuri aproape dispare (I–II 0,633; III–IV 0,615; V–VI 0,606, față de 0,429 / 0,380 / 0,353 "
    "zero-shot). Transferul secvențial păstrează doar o parte din acest câștig (0,464).",
    "Interpretarea este că mai multe imagini ajută doar dacă seamănă cu fotografiile pe care va fi folosit modelul. "
    "Fotografiile clinice din atlase au altă încadrare, altă lumină și o altă compoziție a categoriilor (normal_other "
    "înseamnă mai ales psoriazis), iar modelul reunit își adaptează deciziile la ele, în detrimentul fotografiilor de "
    "telefon. Câștigul mare pe Fitzpatrick17k este un câștig în același domeniu (antrenare și test din aceeași sursă), "
    "nu o îmbunătățire a modelului aplicației. Pentru lucrare rezultă două concluzii: modelul SCIN rămâne cel ales, iar "
    "decalajul pe tonuri de piele observat zero-shot ține în mare parte de schimbarea de domeniu, deoarece dispare "
    "aproape complet când modelul vede date din aceeași sursă.",
]
EN = [
    "The full Fitzpatrick17k image set [{f17k}] (16,577 files) was received from the authors under an obligation to "
    "delete it when the research ends. With it, all 4,012 images that map to the target categories can be used (before, "
    "only 619 could still be downloaded). The images are not redistributed and do not appear in the app, the code "
    "repository or the paper; only aggregate values are reported. Two things were done: the complete external test of "
    "the SCIN model and a new experiment, E7, that checks whether the extra images make the model more accurate.",
    "Complete external test (zero-shot, i.e. without any retraining). The ten E1 photo-only models (one per seed) reach "
    "a macro-F1 of 0.393 ± 0.016 on the 4,012 images, against 0.519 on the SCIN test split. The drop reflects domain "
    "shift: clinical atlas photos differ from SCIN smartphone photos, and normal_other is dominated here by psoriasis. "
    "Performance falls with skin tone: macro-F1 0.412 for eFST I-II, 0.371 for III-IV and 0.312 for V-VI. Among the "
    "categories, redness_rosacea is the weakest (F1 0.237).",
    "Duplicates and photos of the same patient. Fitzpatrick17k contains many near-duplicates [{dups}]: the same photo "
    "re-uploaded, resized, mirrored or cropped, and several photos of the same patient. If one lands in training and "
    "another in the test set, the test score is too high (data leakage). Two checks link images "
    "(`ml/splits/make_fitzpatrick_splits.py`). (a) A 256-bit difference hash (dHash): the image is turned to greyscale "
    "and shrunk to 17 x 16 pixels, and each bit says whether a pixel is brighter than its right neighbour. The Hamming "
    "distance (number of differing bits, 0-256) measures how different two hashes are; two images are linked at a "
    "distance of at most 20. (b) The cosine similarity (between -1 and 1; 1 means the same direction) of ImageNet "
    "features of an EfficientNet-B0 with no skin training; two images are linked at a similarity of at least 0.88. The "
    "threshold was chosen by visual inspection of sampled pairs: above 0.88 nearly every pair showed the same patient or "
    "lesion, below 0.87 unrelated photos became common. Linked images form groups (union-find, a structure that merges "
    "groups as links appear): 588 pairs, 903 images in groups of two or more. For each seed, `StratifiedGroupKFold` (a "
    "five-part split that keeps groups whole and the category mix balanced) puts about 20% of the groups in the "
    "Fitzpatrick17k test fold (803 images); the remaining 3,209 images may be used for training.",
    "Experiment E7 (`ml/run_fitz_pooling.py`) compares the E1 photo-only model with two ways of using the extra images, "
    "with the same network (EfficientNet-B0), the same staged training and the same ten seeds: (1) data pooling: "
    "training on SCIN and the Fitzpatrick17k training fold together, with class weights computed on the pooled set; "
    "(2) sequential transfer: training on Fitzpatrick17k first, then fine-tuning (continuing training at a low learning "
    "rate) on SCIN. Early stopping always uses SCIN validation, because the app's target is smartphone photos. Every "
    "model is tested on the SCIN test split (paired with E1 on the same cases) and on the seed's Fitzpatrick17k test "
    "fold, which it never saw. The experiment is research-only: the model shipped in the app stays SCIN-only.",
    "The results (Table 7) answer no to the question whether the extra images help the app's target. On the SCIN test "
    "split, pooling lowers macro-F1 by 0.035 [-0.071, -0.002] (better in only 2 of 10 seeds; paired t-test p = 0.016), "
    "and balanced accuracy (mean per-category recall) falls from 0.610 to 0.499. Sequential transfer lowers macro-F1 by "
    "0.024 [-0.049, +0.001] (3/10 seeds). By category, pooling raises eczema_dermatitis F1 (+0.042) but lowers "
    "redness_rosacea (-0.107) and acne (-0.057). On the Fitzpatrick17k fold, in contrast, pooling raises macro-F1 from "
    "0.410 (zero-shot) to 0.626 (+0.216, 10/10 seeds), and the skin-tone gap almost disappears (I-II 0.633, III-IV "
    "0.615, V-VI 0.606, against 0.429 / 0.380 / 0.353 zero-shot). Sequential transfer keeps only part of this gain "
    "(0.464).",
    "The interpretation is that more images help only when they resemble the photos the model will be used on. Clinical "
    "atlas photos differ in framing, lighting and category composition (normal_other means mostly psoriasis), and the "
    "pooled model adapts its decisions to them at the expense of smartphone photos. The large gain on Fitzpatrick17k is "
    "an in-domain gain (training and test from the same source), not an improvement of the app model. Two conclusions "
    "follow for the paper: the SCIN-only model remains the chosen one, and the skin-tone gap seen zero-shot is largely "
    "a domain-shift effect, since it nearly vanishes once the model sees data from the same source.",
]

DATA = [  # model, SCIN macro-F1, SCIN diff, Fitz macro-F1, Fitz diff
    ["Photo only, SCIN (E1; zero-shot on Fitzpatrick17k)", "0.519 ± 0.040", "reference", "0.410 ± 0.022", "reference"],
    ["Data pooling (SCIN + Fitzpatrick17k)", "0.484 ± 0.071", "-0.035 [-0.071, -0.002], 2/10",
     "0.626 ± 0.062", "+0.216 [+0.202, +0.231], 10/10"],
    ["Sequential transfer (Fitzpatrick17k, then SCIN)", "0.496 ± 0.051", "-0.024 [-0.049, +0.001], 3/10",
     "0.464 ± 0.049", "+0.053 [+0.042, +0.065], 9/10"],
]
RO_NAMES = ["Doar fotografie, SCIN (E1; zero-shot pe Fitzpatrick17k)", "Reunirea datelor (SCIN + Fitzpatrick17k)",
            "Transfer secvențial (Fitzpatrick17k, apoi SCIN)"]


def ro(s: str) -> str:
    return s.replace(", ", "; ").replace(".", ",").replace("reference", "referință")


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
        ("Teza_Licenta.docx", "8.8 Setul complet Fitzpatrick17k: test extern și antrenare combinată (E7)",
         "Capitolul 9. Concluzii și direcții viitoare", RO,
         [["Model", "Macro-F1 SCIN", "Diferență SCIN", "Macro-F1 Fitzpatrick17k", "Diferență Fitzpatrick17k"]]
         + [[n] + [ro(x) for x in d[1:]] for n, d in zip(RO_NAMES, DATA)],
         "Tabelul 8.8. Experimentul E7 (zece seed-uri; medie ± abatere standard; diferență pereche față de modelul doar "
         "cu fotografie, cu interval bootstrap de 95% și numărul de seed-uri mai bune)."),
        ("Paper_Skin_Concern.docx", "4.8 Full Fitzpatrick17k set: external test and pooled training (E7)",
         "5. Discussion", EN,
         [["Model", "SCIN macro-F1", "SCIN difference", "Fitzpatrick17k macro-F1", "Fitzpatrick17k difference"]] + DATA,
         "Table 7. Experiment E7 (ten seeds; mean ± standard deviation; paired difference against the photo-only model "
         "with 95% bootstrap interval and number of seeds better).")):
    ed = DocEditor(str(ROOT / "docs" / path))
    if ed.has_heading(head):
        print(path, "already updated")
        continue
    n = {"f17k": ed.add_reference(F17K[1], F17K[0]), "dups": ed.add_reference(DUPS[1], DUPS[0])}
    anchor = ed.heading(next_head)
    ed.heading_before(anchor, head, 2)
    for t in paras[:4]:
        ed.body_paragraph_before(anchor, t.format(**n))
    add_table(ed, anchor, rows, cap)
    for t in paras[4:]:
        ed.body_paragraph_before(anchor, t.format(**n))
    try:
        ed.save()
        print(path, "updated")
    except PermissionError:
        print(path, "LOCKED (open in Word) - not updated")
