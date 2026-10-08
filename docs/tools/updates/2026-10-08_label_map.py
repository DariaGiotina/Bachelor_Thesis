import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocAppender  # noqa: E402

ROWS = [
    ["Categorie", "eFST I–II", "eFST III–IV", "eFST V–VI", "eFST lipsă", "Total"],
    ["acne", "55", "77", "10", "2", "144"],
    ["eczema_dermatitis", "478", "460", "89", "41", "1.068"],
    ["redness_rosacea", "30", "11", "1", "2", "44"],
    ["normal_other", "216", "258", "49", "30", "553"],
    ["excluded", "994", "1.355", "287", "588", "3.224"],
]

t = DocAppender(str(ROOT / "docs" / "Teza_Capitolul1_Introducere.docx"), "Bibliografie")
H = "5.2 Definirea categoriilor țintă de probleme ale pielii"
if not t.has_heading(H):
    t.heading(H, level=2)
    t.para(
        "Etichetele SCIN sunt peste 370 de denumiri diferențiale distincte, multe cu mai puțin de zece apariții, deci "
        "nepotrivite ca set de clase pentru un asistent informativ. Scriptul ml/labels/build_labels.py le grupează în "
        "cinci categorii țintă (acne, eczema_dermatitis, redness_rosacea, normal_other, excluded), pe baza unui "
        "dicționar explicit din ml/labels/label_map.yaml. Pentru fiecare case_id, ponderile denumirilor atribuite "
        "aceleiași categorii se însumează, iar categoria cu suma maximă devine eticheta principală dacă suma atinge un "
        "prag configurabil (0,40). Egalitățile și cazurile sub prag primesc eticheta excluded, la fel ca denumirile "
        "nemapate. Categoriile sunt grupări de probleme ale pielii, nu clasificări medicale."
    )
    t.para(
        "Din 5.033 de cazuri, 144 au ca etichetă principală acne, 1.068 eczema_dermatitis, 44 redness_rosacea și 553 "
        "normal_other; 3.224 sunt excluse (dintre acestea, 1.972 nu au nicio etichetă ponderată). Categoria "
        "redness_rosacea are doar un caz în grupul eFST V–VI, iar acne 10 (Tabelul 5.2), deci analiza pe tonuri închise "
        "va avea intervale de încredere foarte largi pentru aceste categorii. Mapările din label_map.yaml sunt decizii "
        "ale autorului (de exemplu foliculita este inclusă în acne) și vor fi raportate ca limitare."
    )
    t.table(ROWS, caption="Tabelul 5.2. Categorii țintă pe grupe eFST (SCIN, prag 0,40).")
    try:
        t.save()
        print("thesis updated")
    except PermissionError:
        print("THESIS LOCKED (open in Word) - not updated")

p = DocAppender(str(ROOT / "docs" / "Paper_Introduction.docx"), "References")
H = "3.2 Target skin-concern categories"
if not p.has_heading(H):
    p.heading(H, level=2)
    p.para(
        "SCIN condition strings number over 370 distinct dermatologist differentials, most of them rare, so we group "
        "them into five target categories: acne, eczema_dermatitis, redness_rosacea, normal_other and excluded "
        "(ml/labels/label_map.yaml, built by ml/labels/build_labels.py). For each case_id, the weights of strings "
        "mapped to the same category are summed; the category with the largest sum becomes the primary label if the sum "
        "reaches a configurable threshold (0.40). Ties, sub-threshold cases and unmapped strings are labelled "
        "excluded. These are coarse skin-concern groupings, not clinical classes."
    )
    p.para(
        "Of 5,033 cases, 144 are acne, 1,068 eczema_dermatitis, 44 redness_rosacea, 553 normal_other and 3,224 "
        "excluded (1,972 of which have no weighted label). Only 10 acne and 1 redness_rosacea cases fall in eFST V–VI "
        "(Table 2), so per-tone estimates for these categories will have very wide confidence intervals. The string-to-"
        "category mapping is an author decision (e.g. folliculitis is grouped with acne) and is a limitation."
    )
    p.table(
        [[c.replace("Categorie", "Category").replace("lipsă", "missing").replace(".", ",") if i == 0 else c.replace(".", ",")
          for c in r] for i, r in enumerate(ROWS)],
        caption="Table 2. Target categories by eFST group (SCIN, threshold 0.40).",
    )
    p.save()
print("ok")
