import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocAppender  # noqa: E402

REPO = "https://github.com/google-research-datasets/scin"
LIC = "https://github.com/google-research-datasets/scin/blob/main/LICENSE"
BLOG = "https://research.google/blog/scin-a-new-resource-for-representative-dermatology-images/"
SCHEMA = "https://github.com/google-research-datasets/scin/blob/main/dataset_schema.md"

# ------------------------------------------------------------------ thesis (RO)
t = DocAppender(str(ROOT / "docs" / "Teza_Capitolul1_Introducere.docx"), "Bibliografie")
H = "5.1 Setul de date SCIN: obținere, licență și audit"
if not t.has_heading(H):
    t.reference("Google Research, SCIN: Skin Condition Image Network, depozit GitHub", REPO)
    t.reference("Google Research, SCIN Data Use License", LIC)
    t.reference("Google Research, documentația schemei setului de date SCIN", SCHEMA)
    t.reference("Google Research Blog, SCIN: A new resource for representative dermatology images", BLOG)
    r, l, s, b = (t.ref_number(u) for u in (REPO, LIC, SCHEMA, BLOG))

    t.heading("Capitolul 5. Metodologia AI/ML (ciornă)", level=1)
    t.heading(H, level=2)
    t.para(
        f"Setul de date principal al lucrării este SCIN (Skin Condition Image Network), publicat de Google Research "
        f"({REPO}) [{r}]. Setul a fost colectat prin contribuții voluntare ale unor utilizatori din Statele Unite, "
        f"care au trimis fotografii realizate cu telefonul, împreună cu răspunsuri auto-declarate despre simptome, "
        f"textură, durată și date demografice ({BLOG}) [{b}]. Metadatele sunt distribuite sub forma a două fișiere CSV "
        f"principale, scin_cases.csv și scin_labels.csv, legate prin identificatorul case_id, alături de două fișiere "
        f"care descriu întrebările din aplicație și din procesul de etichetare ({SCHEMA}) [{s}]. Fișierele au fost "
        f"descărcate din depozitul public Google Cloud Storage dx-scin-public-data, versiunea 1.0.0."
    )
    t.para(
        f"Utilizarea datelor este reglementată de SCIN Data Use License ({LIC}) [{l}]. Licența permite reproducerea, "
        f"partajarea și adaptarea materialului, cu condiția atribuirii sursei, și interzice explicit orice încercare de "
        f"re-identificare a persoanelor ale căror date au fost de-identificate; nerespectarea acestei restricții duce la "
        f"încetarea imediată a drepturilor acordate. În consecință, lucrarea folosește datele exclusiv în scop de "
        f"cercetare, nu redistribuie imaginile și nu efectuează nicio prelucrare care ar putea conduce la "
        f"re-identificare."
    )
    t.para(
        "Pentru a cunoaște structura și limitările datelor înainte de proiectarea modelului, a fost implementat scriptul "
        "ml/scripts/audit_scin.py. Acesta încarcă cele două fișiere, verifică unicitatea și corespondența "
        "identificatorului case_id, unește tabelele la nivel de caz și generează o schemă a coloanelor "
        "(scin_schema.json), un raport de audit (scin_audit_report.md) și o intrare în registrul surselor de date "
        "(data_sources.csv). Un aspect metodologic important este faptul că întrebările cu răspunsuri multiple "
        "(textură, zonă a corpului, simptome) sunt stocate câte o coloană pentru fiecare opțiune, cu valoarea „YES” sau "
        "necompletată; o celulă goală înseamnă „opțiune nebifată”, nu „valoare lipsă”. De aceea, lipsa răspunsurilor a "
        "fost evaluată la nivelul întregii întrebări, iar răspunsurile neinformative, precum AGE_UNKNOWN sau "
        "OTHER_OR_UNSPECIFIED, au fost raportate separat de valorile absente."
    )
    t.para(
        "Auditul a identificat 5.033 de cazuri unice și 10.407 imagini, în medie 2,07 imagini per caz; 38,7% dintre "
        "cazuri au o singură imagine, 15,8% au două, iar 45,5% au trei. Toate cele 5.033 de identificatoare apar în "
        "ambele fișiere, fără duplicate. Lipsa răspunsurilor este substanțială și neuniformă: grupa de vârstă este "
        "necunoscută în 56,9% dintre cazuri, tipul de piele Fitzpatrick auto-declarat lipsește sau este neidentificat în "
        "56,8%, întrebarea despre etnie nu are niciun răspuns în 47,3%, simptomele legate de afecțiune lipsesc în 25,1%, "
        "durata în 20,6%, iar textura și zona corpului în aproximativ 19% dintre cazuri. Această lipsă naturală a "
        "răspunsurilor confirmă relevanța practică a întrebării de cercetare privind funcționarea modelului atunci când "
        "chestionarul este incomplet."
    )
    t.table([
        ["Grupă", "Cazuri", "Procent"],
        ["eFST I–II", "1.773", "35,2%"],
        ["eFST III–IV", "2.161", "42,9%"],
        ["eFST V–VI", "436", "8,7%"],
        ["eFST lipsă", "663", "13,2%"],
        ["eMST 1–3 (adnotatori SUA)", "3.502", "69,6%"],
        ["eMST 4–6 (adnotatori SUA)", "1.296", "25,8%"],
        ["eMST 7–10 (adnotatori SUA)", "207", "4,1%"],
    ], caption="Tabelul 5.1. Distribuția tonurilor de piele estimate în SCIN (N = 5.033 cazuri).")
    t.para(
        "Distribuția tonurilor de piele este dezechilibrată (Tabelul 5.1). Tonul Fitzpatrick estimat de dermatologi "
        "(eFST) a fost calculat ca mediana celor până la trei etichete disponibile pentru fiecare caz; în 73,7% dintre "
        "cazuri există o singură etichetă, iar 13,2% dintre cazuri nu au niciuna. Grupul V–VI reprezintă doar 8,7% din "
        "cazuri, iar tipul VI numai 68 de cazuri (1,35%). Pe scala Monk (eMST), grupul 7–10 cuprinde 4,1% din cazuri "
        "conform adnotatorilor din SUA și doar 1,0% conform celor din India, ceea ce arată că cele două grupuri de "
        "adnotatori nu sunt interschimbabile și că alegerea uneia dintre ele trebuie raportată explicit. Rezultatele "
        "pentru tonurile închise vor avea, prin urmare, intervale de încredere largi."
    )
    t.para(
        "În privința etichetelor, 3.061 de cazuri (60,8%) au cel puțin o etichetă ponderată atribuită de dermatologi, "
        "iar primul dermatolog a considerat calitatea imaginilor insuficientă pentru o evaluare în 38,3% dintre cazuri. "
        "Etichetele reprezintă evaluări diferențiale retrospective, realizate pe baza imaginilor și a datelor "
        "auto-declarate, nu rezultate confirmate clinic. Cele mai frecvente etichete principale sunt eczema (488 de "
        "cazuri), dermatita alergică de contact (270), urticaria (214), înțepătura de insectă (185) și foliculita (142), "
        "în timp ce acneea apare ca etichetă principală în doar 61 de cazuri, iar rozaceea în 29. Aceste valori vor "
        "fundamenta alegerea setului final de clase. Împărțirea în seturi de antrenare, validare și testare se va face "
        "la nivel de caz (case_id), astfel încât imaginile aceluiași caz să nu apară în seturi diferite."
    )
    try:
        t.save()
        print("thesis updated")
    except PermissionError:
        print("THESIS LOCKED (open in Word) - not updated")

# ------------------------------------------------------------------- paper (EN)
p = DocAppender(str(ROOT / "docs" / "Paper_Introduction.docx"), "References")
H = "3.1 SCIN dataset and audit"
if not p.has_heading(H):
    p.reference("Google Research, SCIN: Skin Condition Image Network, GitHub repository", REPO)
    p.reference("Google Research, SCIN Data Use License", LIC)
    p.reference("Google Research, SCIN dataset schema documentation", SCHEMA)
    r, l, s = (p.ref_number(u) for u in (REPO, LIC, SCHEMA))

    p.heading("3. Data (draft)", level=1)
    p.heading(H, level=2)
    p.para(
        f"We use SCIN (Skin Condition Image Network) release 1.0.0 [{r}] ({REPO}), a crowdsourced dataset of "
        f"smartphone photographs contributed by US users together with self-reported symptoms, texture, duration and "
        f"demographics. Case-level metadata are distributed as scin_cases.csv and scin_labels.csv, joined on case_id "
        f"[{s}]. SCIN is released under the SCIN Data Use License [{l}] ({LIC}), which permits sharing and adaptation "
        f"with attribution and prohibits any attempt to re-identify data subjects; we use the data for research only "
        f"and do not redistribute images."
    )
    p.para(
        "We audited the metadata with a reproducible script (ml/scripts/audit_scin.py) before any modelling. The "
        "dataset contains 5,033 unique cases and 10,407 images (mean 2.07 per case; 38.7% of cases have one image, "
        "15.8% two and 45.5% three); every case_id appears exactly once in both files. Multi-select questions are "
        "encoded as one YES/blank column per option, so a blank cell means an unticked option rather than a missing "
        "value; we therefore measure missingness per question. Uninformative answers (e.g. AGE_UNKNOWN, "
        "OTHER_OR_UNSPECIFIED) are counted separately from absent values."
    )
    p.para(
        "Natural missingness is high and uneven across fields: age group is unknown for 56.9% of cases, self-reported "
        "Fitzpatrick type is absent or unidentified for 56.8%, the race/ethnicity question is unanswered for 47.3%, "
        "condition symptoms for 25.1%, duration for 20.6%, and texture and body location for about 19%. Real users "
        "thus leave a large share of questionnaire items empty, which motivates RQ2."
    )
    p.table([
        ["Group", "Cases", "%"],
        ["eFST I–II", "1,773", "35.2"],
        ["eFST III–IV", "2,161", "42.9"],
        ["eFST V–VI", "436", "8.7"],
        ["eFST missing", "663", "13.2"],
        ["eMST 1–3 (US annotators)", "3,502", "69.6"],
        ["eMST 4–6 (US annotators)", "1,296", "25.8"],
        ["eMST 7–10 (US annotators)", "207", "4.1"],
    ], caption="Table 1. Estimated skin-tone distribution in SCIN (N = 5,033 cases).")
    p.para(
        "We define eFST as the median of up to three dermatologist Fitzpatrick labels per case, rounded half up; 73.7% "
        "of cases have a single label and 13.2% have none. Darker tones are under-represented (Table 1): eFST V–VI "
        "covers 8.7% of cases and type VI only 68 cases (1.35%). On the Monk scale, eMST 7–10 covers 4.1% of cases "
        "according to US annotators but only 1.0% according to India annotators, so the annotator pool must be fixed "
        "and reported. Estimates for darker groups will carry wide confidence intervals."
    )
    p.para(
        "Weighted dermatologist condition labels are available for 3,061 cases (60.8%); the first dermatologist rated "
        "image quality insufficient for 38.3% of cases. These labels are retrospective differential assessments, not "
        "clinically confirmed outcomes, and our metrics therefore measure agreement with dermatologist labels. The most "
        "frequent top-weighted labels are eczema (488), allergic contact dermatitis (270), urticaria (214), insect bite "
        "(185) and folliculitis (142), while acne (61) and rosacea (29) are rare; these counts will constrain the final "
        "class set. All splits are made at the case level so that images of one case never cross splits."
    )
    p.save()
print("ok")
