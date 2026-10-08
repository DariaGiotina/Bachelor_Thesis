import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocAppender  # noqa: E402

t = DocAppender(str(ROOT / "docs" / "Teza_Capitolul1_Introducere.docx"), "Bibliografie")
H = "5.5 Împărțirea pe cazuri în seturi de antrenare, validare și testare"
if not t.has_heading(H):
    t.heading(H, level=2)
    t.para(
        "Datele sunt împărțite în trei seturi: antrenare (70%, pe care modelul învață), validare (15%, pentru alegerea "
        "setărilor) și testare (15%, folosit doar pentru evaluarea finală). Împărțirea se face la nivel de caz "
        "(case_id), nu de imagine: toate fotografiile aceluiași caz rămân în același set. Altfel, apare scurgerea de "
        "informație (data leakage): modelul ar vedea la antrenare o fotografie a unui caz și ar fi testat pe o altă "
        "fotografie a aceluiași caz, iar rezultatele ar fi nerealist de bune. Scriptul ml/splits/make_splits.py lucrează "
        "pe un rând per case_id, deci un caz nu poate fi împărțit între seturi."
    )
    t.para(
        "Împărțirea este stratificată, adică păstrează în fiecare set aproximativ aceleași proporții ale unei "
        "combinații de două variabile: categoria țintă (primary_label) și grupa de ton eFST (I–II, III–IV, V–VI sau "
        "lipsă). Astfel, tonurile închise nu ajung accidental doar într-un singur set. Se face în doi pași: mai întâi "
        "70% antrenare și 30% rest, apoi restul se împarte în jumătate între validare și testare. Combinațiile cu mai "
        "puțin de 4 cazuri nu pot fi stratificate; ele sunt unite mai întâi pe categorie, apoi într-un grup comun "
        "(5 cazuri în total). Procedura se repetă pentru cinci valori ale seed-ului (0–4), adică ale numărului care "
        "fixează aleatorismul, ceea ce dă cinci împărțiri diferite și reproductibile, pentru raportarea variabilității "
        "rezultatelor."
    )
    t.para(
        "Rezultatul este 3.523 de cazuri în antrenare, 755 în validare și 755 în testare pentru fiecare seed. În "
        "grupul eFST V–VI cazurile se repartizează 305, 66 și 65. Categoria redness_rosacea are în total 44 de cazuri "
        "(31 în antrenare, 7 în validare, 6 în testare, pentru seed-ul 0), iar în V–VI un singur caz, în antrenare, "
        "deci rezultatele pentru ea pe tonuri închise nu pot fi evaluate. Un test automat (ml/tests/test_no_leakage.py) "
        "verifică pentru fiecare seed că niciun case_id nu apare în două seturi, că nu există duplicate și că seturile "
        "acoperă toate cazurile."
    )
    try:
        t.save()
        print("thesis updated")
    except PermissionError:
        print("THESIS LOCKED (open in Word) - not updated")

p = DocAppender(str(ROOT / "docs" / "Paper_Introduction.docx"), "References")
H = "3.5 Case-level train/validation/test splits"
if not p.has_heading(H):
    p.heading(H, level=2)
    p.para(
        "We split the data into train (70%, where the model learns), validation (15%, for choosing settings) and test "
        "(15%, used only for final evaluation). The split is made at the case level (case_id), not the image level: "
        "all photographs of a case stay in one split. Otherwise data leakage occurs: the model would see one photo of "
        "a case during training and be tested on another photo of the same case, inflating the results. The script "
        "(ml/splits/make_splits.py) works on one row per case_id, so a case cannot be divided between splits."
    )
    p.para(
        "The split is stratified, meaning each split keeps roughly the same proportions of a combined variable: target "
        "category (primary_label) times eFST group (I-II, III-IV, V-VI or missing), so darker skin tones do not end up "
        "in a single split by chance. It is done in two steps: 70% train versus 30% rest, then the rest is halved into "
        "validation and test. Combinations with fewer than 4 cases cannot be stratified; they are merged first by "
        "category and then into one shared group (5 cases in total). The procedure is repeated for five seeds (0-4), "
        "the numbers that fix the randomness, which gives five different reproducible splits for reporting the "
        "variability of results."
    )
    p.para(
        "Each seed yields 3,523 train, 755 validation and 755 test cases. In eFST V-VI the cases split 305, 66 and 65. "
        "The redness_rosacea category has 44 cases in total (31, 7 and 6 for seed 0) and only one case in V-VI, in the "
        "training split, so its per-tone performance cannot be evaluated. An automated test "
        "(ml/tests/test_no_leakage.py) checks for every seed that no case_id appears in two splits, that there are no "
        "duplicates and that the splits cover every case."
    )
    p.save()
print("ok")
