import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocAppender  # noqa: E402

SCHEMA = "https://github.com/google-research-datasets/scin/blob/main/dataset_schema.md"

t = DocAppender(str(ROOT / "docs" / "Teza_Capitolul1_Introducere.docx"), "Bibliografie")
H = "5.4 Codificarea chestionarului și masca de valori lipsă"
if not t.has_heading(H):
    s = t.ref_number(SCHEMA)
    t.heading(H, level=2)
    t.para(
        f"Răspunsurile auto-declarate din SCIN [{s}] sunt transformate într-un vector numeric de lungime fixă, "
        f"împreună cu o mască binară de valori lipsă. Masca (mask) conține câte o valoare pentru fiecare câmp al "
        f"chestionarului: 1 înseamnă că persoana nu a răspuns, 0 că a răspuns. Valorile lipsă nu sunt completate "
        f"(imputare, adică înlocuirea lor cu o valoare estimată, de exemplu media); în schimb, câmpul lipsă primește "
        f"valoarea 0 în vector, iar modelul citește masca pentru a ști că acel 0 nu este un răspuns. Această alegere "
        f"permite experimente în care răspunsurile sunt eliminate deliberat (modality dropout) și măsurarea "
        f"robusteții modelului la răspunsuri lipsă."
    )
    t.para(
        "Un răspuns explicit de tip „necunoscut” sau „niciuna dintre variante” este tratat ca răspuns prezent (masca 0) "
        "și are propria coloană indicator, deosebit de lipsa răspunsului. Șase câmpuri sunt codificate: grupa de vârstă "
        "și tipul de piele auto-declarat (one-hot: câte o coloană pentru fiecare variantă, exact una având valoarea 1), "
        "zona corpului, simptomele și textura (multi-hot: câte o coloană pentru fiecare variantă, mai multe putând fi 1, "
        "deoarece persoana poate bifa mai multe opțiuni) și durata (ordinală: număr întreg de la 1, „o zi”, la 8, "
        "„din copilărie”, păstrând ordinea). Rezultă 40 de coloane de trăsături și 6 de mască pentru fiecare case_id."
    )
    t.para(
        "Întrebările cu răspunsuri multiple sunt stocate în SCIN ca o coloană pe opțiune, cu valoarea „YES” sau celulă "
        "goală. O celulă goală înseamnă „nebifat”, deci o întrebare este considerată fără răspuns doar dacă nu este "
        "bifată nicio opțiune; nu se poate distinge între o persoană care a omis întrebarea și una care nu a bifat nimic "
        "(limitare). Rata observată a lipsei este de 18,8% pentru zona corpului, 25,1% pentru simptome, 19,0% pentru "
        "textură, 19,8% pentru durată și 50,3% pentru tipul de piele; încă 328 de cazuri au ales „niciuna dintre "
        "variante” la tipul de piele. Sexul la naștere, etnia, simptomele sistemice și categoria auto-descrisă nu sunt "
        "incluse: primele două sunt rezervate analizei de echitate, iar ultima conține etichete precum „acne”, care ar "
        "dezvălui clasa țintă."
    )
    try:
        t.save()
        print("thesis updated")
    except PermissionError:
        print("THESIS LOCKED (open in Word) - not updated")

p = DocAppender(str(ROOT / "docs" / "Paper_Introduction.docx"), "References")
H = "3.4 Questionnaire encoding and missingness mask"
if not p.has_heading(H):
    s = p.ref_number(SCHEMA)
    p.heading(H, level=2)
    p.para(
        f"Self-reported SCIN answers [{s}] are encoded as a fixed-length numeric vector plus a binary missingness mask. "
        f"The mask has one entry per questionnaire field: 1 means the question was not answered and 0 that it was. "
        f"We do not impute (replace missing values with an estimate such as the mean); a missing field is set to 0 in "
        f"the vector and the model reads the mask to know that this 0 is not an answer. This allows experiments that "
        f"drop answers on purpose (modality dropout) and measures robustness to missing answers."
    )
    p.para(
        "An explicit \"unknown\" or \"none of the above\" answer counts as present (mask 0) and has its own indicator "
        "column, distinct from a missing answer. Six fields are encoded: age group and self-reported skin type "
        "(one-hot: one column per option, exactly one equal to 1), body area, symptoms and texture (multi-hot: one "
        "column per option, several can be 1 because respondents may tick more than one) and duration (ordinal: an "
        "integer from 1, one day, to 8, since childhood, preserving order). This gives 40 feature columns and 6 mask "
        "columns per case_id."
    )
    p.para(
        "Multi-select questions are stored in SCIN as one column per option holding YES or blank. A blank cell means "
        "not ticked, so a question counts as unanswered only when no option is ticked; a respondent who skipped the "
        "question cannot be distinguished from one who ticked nothing (a limitation). Observed missing rates are 18.8% "
        "for body area, 25.1% for symptoms, 19.0% for texture, 19.8% for duration and 50.3% for skin type, with a "
        "further 328 cases answering \"none of the above\" for skin type. Sex at birth, race/ethnicity, systemic "
        "symptoms and the self-described category are excluded: the first two are reserved for fairness analysis and "
        "the last contains labels such as \"acne\" that would leak the target class."
    )
    p.save()
print("ok")
