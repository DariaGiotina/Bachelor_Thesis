import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocAppender  # noqa: E402

FITZ = "https://doi.org/10.1001/archderm.1988.01670060015008"
MONK = "https://skintone.google/"
SCHEMA = "https://github.com/google-research-datasets/scin/blob/main/dataset_schema.md"

t = DocAppender(str(ROOT / "docs" / "Teza_Capitolul1_Introducere.docx"), "Bibliografie")
H = "5.3 Scalele de ton al pielii și grupele folosite"
if not t.has_heading(H):
    t.reference("Fitzpatrick, T. B., The validity and practicality of sun-reactive skin types I through VI, "
                "Archives of Dermatology 124(6), 1988, 869–871", FITZ)
    t.reference("Google Research, Monk Skin Tone Scale", MONK)
    f, m, s = (t.ref_number(u) for u in (FITZ, MONK, SCHEMA))
    t.heading(H, level=2)
    t.para(
        f"Scala Fitzpatrick (FST) clasifică pielea în șase tipuri, de la I la VI, după reacția la soare: tipul I "
        f"(piele foarte deschisă) se arde mereu și nu se bronzează, tipul III se arde uneori și se bronzează treptat, "
        f"iar tipul VI (piele foarte închisă) aproape nu se arde niciodată ({FITZ}) [{f}]. În SCIN, până la trei "
        f"dermatologi au atribuit fiecărui caz o etichetă FST pe baza fotografiilor [{s}]. Din acestea am calculat "
        f"eFST (estimated Fitzpatrick skin type, tip Fitzpatrick estimat) ca mediană a etichetelor disponibile, "
        f"rotunjită în sus la jumătate. eFST este o estimare a unui evaluator pe baza unei fotografii, nu o măsurătoare "
        f"a pielii, și este influențată de iluminare."
    )
    t.para(
        "Deoarece tipurile individuale au prea puține cazuri (tipul VI are doar 68), le-am grupat în perechi: "
        "I–II (piele cea mai deschisă, 1.773 de cazuri), III–IV (piele medie, 2.161 de cazuri) și V–VI (piele cea mai "
        "închisă, 436 de cazuri); 663 de cazuri nu au nicio etichetă FST și formează grupa „lipsă”."
    )
    t.para(
        f"A doua scală, eMST (estimated Monk Skin Tone), folosește cele 10 trepte ale scalei Monk ({MONK}) [{m}], "
        f"atribuite de adnotatori. Am grupat-o în 1–3 (deschis), 4–6 (mediu) și 7–10 (închis). eMST nu este "
        f"echivalentă cu eFST: cele două scale sunt măsuri diferite ale tonului pielii și sunt raportate separat."
    )
    try:
        t.save(); print("thesis updated")
    except PermissionError:
        print("THESIS LOCKED (open in Word) - not updated")

p = DocAppender(str(ROOT / "docs" / "Paper_Introduction.docx"), "References")
H = "3.3 Skin-tone scales and groups"
if not p.has_heading(H):
    p.reference("T. B. Fitzpatrick, The validity and practicality of sun-reactive skin types I through VI, "
                "Archives of Dermatology 124(6), 1988, 869–871", FITZ)
    p.reference("Google Research, Monk Skin Tone Scale", MONK)
    f, m, s = (p.ref_number(u) for u in (FITZ, MONK, SCHEMA))
    p.heading(H, level=2)
    p.para(
        f"The Fitzpatrick scale (FST) classifies skin into six types by its reaction to sun: type I (very pale skin) "
        f"always burns and never tans, type III sometimes burns and tans gradually, and type VI (very dark skin) "
        f"almost never burns ({FITZ}) [{f}]. In SCIN, up to three dermatologists assigned each case an FST label "
        f"from the photographs [{s}]. We define eFST (estimated Fitzpatrick skin type) as the median of the available "
        f"labels, rounded half up. eFST is a rater's estimate from a photograph, not a measurement of the skin, and "
        f"is affected by lighting."
    )
    p.para(
        "Because single types are sparse (type VI has only 68 cases), we pair them: I–II (lightest skin, 1,773 "
        "cases), III–IV (medium skin, 2,161 cases) and V–VI (darkest skin, 436 cases). The 663 cases with no FST "
        "label form a separate missing group."
    )
    p.para(
        f"The second scale, eMST (estimated Monk Skin Tone), uses the 10-point Monk scale ({MONK}) [{m}] as rated by "
        f"annotators; we group it as 1–3 (light), 4–6 (medium) and 7–10 (dark). eMST is not equivalent to eFST: the "
        f"two are different measures of skin tone and are reported separately."
    )
    p.save()
print("ok")
