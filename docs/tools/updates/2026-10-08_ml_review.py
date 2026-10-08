"""Apply the ML review fixes to the thesis and the paper.

- 5.6 / 3.6: duplicate-image grouping in the splits and the new split sizes
- 5.7 / 3.7: aspect-preserving resize (letterbox) and the new seed-0 counts
- 5.8 / 3.8: a missing questionnaire is all-masked at inference too
- 5.10 / 3.9: field-level hiding on top of natural missingness, per-group macro-F1, bootstrap CIs
"""
import sys
from pathlib import Path

from docx.text.paragraph import Paragraph

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocEditor  # noqa: E402

BOOT = "https://doi.org/10.1201/9780429246593"
BOOT_REF = "B. Efron, R. J. Tibshirani, An Introduction to the Bootstrap, Chapman & Hall/CRC, 1993"


def par(ed: DocEditor, start: str) -> Paragraph:
    return next(p for p in ed.doc.paragraphs if p.text.startswith(start))


def insert_after(ed: DocEditor, start: str, text: str) -> None:
    p = par(ed, start)
    nxt = Paragraph(p._p.getnext(), p._parent)
    ed.body_paragraph_before(nxt, text)


def fix(ed: DocEditor, lang: str) -> None:
    ro = lang == "ro"
    n = ed.add_reference(BOOT_REF, BOOT)
    rep = ed.replace_in_paragraph
    if ro:
        s = "Rezultatul este"
        rep(s, "Rezultatul este 3.523 de cazuri în antrenare, 755 în validare și 755 în testare pentru fiecare seed.",
            "Rezultatul este, în funcție de seed, între 3.522 și 3.525 de cazuri în antrenare, între 754 și 757 în "
            "validare și între 754 și 756 în testare.")
        rep(s, "se repartizează 305, 66 și 65.", "se repartizează 303, 68 și 65 (seed-ul 0).")
        rep(s, "(31 în antrenare, 7 în validare, 6 în testare, pentru seed-ul 0), iar în V–VI un singur caz, în antrenare,",
            "(30 în antrenare, 8 în validare, 6 în testare, pentru seed-ul 0), iar în V–VI un singur caz, în validare,")
        rep(s, "că nu există duplicate și că seturile acoperă toate cazurile.",
            "că nu există duplicate, că seturile acoperă toate cazurile și că nicio fotografie identică nu apare în "
            "două seturi.")
        insert_after(ed, "Împărțirea este stratificată",
                     "Pe lângă cazurile propriu-zise, s-a verificat dacă aceeași fotografie apare în mai multe cazuri: "
                     "pentru toate cele 4.089 de imagini descărcate (inclusiv toate cele 3.886 ale cazurilor folosite) "
                     "s-a calculat amprenta MD5, un cod care este identic doar pentru fișiere identice (scriptul "
                     "`ml/scripts/find_duplicate_images.py`). Au rezultat 5 grupuri de câte 2–3 cazuri (12 cazuri în "
                     "total) care conțin aceleași fotografii, probabil același contributor care a trimis cazul de două "
                     "ori. În prima versiune a împărțirii, pentru seed-ul 0, patru astfel de fotografii ajungeau în seturi "
                     "diferite, deci modelul ar fi putut vedea la antrenare o imagine de test. De aceea, cazurile unui "
                     "grup sunt tratate ca o singură unitate la împărțire. Într-un grup, aceleași fotografii au primit "
                     "categorii diferite (redness_rosacea, eczema_dermatitis și excluded), un exemplu concret de zgomot în "
                     "etichete, adică etichete inconsecvente pentru aceeași imagine.")
        rep("Pentru antrenare, datele", "1.266 în antrenare, 272 în validare și 271 în testare.",
            "1.266 în antrenare, 273 în validare și 270 în testare.")
        rep("Augmentarea înseamnă", "Toate seturile sunt redimensionate la 224×224 pixeli și normalizate",
            "Toate seturile sunt aduse la 224×224 pixeli păstrând proporțiile: latura mai lungă este scalată la 224 de "
            "pixeli, iar spațiul rămas este completat cu negru (letterbox). Majoritatea fotografiilor SCIN sunt în format "
            "portret 3:4, iar întinderea lor la un pătrat ar deforma leziunile. Imaginile sunt apoi normalizate")
        rep("Augmentarea înseamnă", "nu primesc nicio augmentare în afară de aceste două operații.",
            "nu primesc nicio augmentare în afară de aceste operații.")
        rep("Modelul combină două ramuri", "(46 de numere).",
            "(46 de numere). Dacă chestionarul lipsește complet, modelul primește trăsături 0 și toate valorile măștii "
            "egale cu 1, aceeași reprezentare ca la antrenare, deci un chestionar absent nu este confundat cu unul "
            "completat cu răspunsuri 0.")
        rep("Evaluarea se face", "raportate global și separat pe grupele eFST (I–II, III–IV, V–VI, lipsă), împreună "
            "cu diferența maximă dintre grupe.",
            "raportate global și separat pe grupele eFST (I–II, III–IV, V–VI, lipsă), împreună cu diferența maximă "
            "dintre grupele de ton (I–II, III–IV, V–VI; grupa „lipsă” nu este un ton). Într-o grupă, macro-F1 se "
            "calculează doar pe categoriile care apar în ea (de exemplu, redness_rosacea nu are cazuri V–VI în "
            "testare). Pentru fiecare valoare se raportează un interval de încredere de 95% obținut prin bootstrap "
            f"[{n}], adică prin reeșantionarea repetată (de 1.000 de ori) a cazurilor de test cu înlocuire; intervalele "
            "arată cât de sigure sunt rezultatele pe grupele mici.")
        rep("Evaluarea se face", "dintre câmpurile chestionarului ascunse,",
            "dintre câmpurile chestionarului ascunse (fiecare câmp independent, în plus față de răspunsurile care "
            "lipsesc deja în date; la 100% chestionarul este ascuns complet),")
    else:
        s = "Each seed yields"
        rep(s, "Each seed yields 3,523 train, 755 validation and 755 test cases.",
            "Depending on the seed, the splits hold 3,522-3,525 train, 754-757 validation and 754-756 test cases.")
        s = "Depending on the seed"
        rep(s, "the cases split 305, 66 and 65.", "the cases split 303, 68 and 65 (seed 0).")
        rep(s, "(31, 7 and 6 for seed 0) and only one case in V–VI, in the training split,",
            "(30, 8 and 6 for seed 0) and only one case in V–VI, in the validation split,")
        rep(s, "that there are no duplicates and that the splits cover every case.",
            "that there are no duplicates, that the splits cover every case and that no identical photograph is in "
            "two splits.")
        insert_after(ed, "The split is stratified",
                     "Beyond case identity, we checked whether the same photograph appears in more than one case: we "
                     "computed the MD5 hash, a code that is identical only for identical files, of all 4,089 downloaded "
                     "images, including all 3,886 images of the cases used (`ml/scripts/find_duplicate_images.py`). This "
                     "found 5 groups of 2-3 cases (12 cases in total) sharing the same photographs, most likely the same "
                     "contributor submitting a case twice. In the first version of the split, four such photographs fell "
                     "into different splits for seed 0, so a test image could have been seen in training. The cases of a "
                     "group are therefore treated as one unit when splitting. In one group the same photographs received "
                     "different categories (redness_rosacea, eczema_dermatitis and excluded), a concrete example of label "
                     "noise, i.e. inconsistent labels for the same image.")
        rep("Training data are served", "1,266 train, 272 validation and 271 test cases.",
            "1,266 train, 273 validation and 270 test cases.")
        rep("Augmentation means", "All splits are resized to 224×224 pixels and normalised",
            "All splits are brought to 224×224 pixels while keeping the aspect ratio: the longer side is scaled to "
            "224 pixels and the remaining space is padded with black (letterbox). Most SCIN photographs are portrait "
            "3:4, and stretching them to a square would distort lesions. Images are then normalised")
        rep("Augmentation means", "receive no augmentation beyond these two steps.",
            "receive no augmentation beyond these steps.")
        rep("The model combines two branches", "(46 numbers).",
            "(46 numbers). When the questionnaire is missing entirely, the model receives zero features and an "
            "all-ones mask, the same representation as in training, so an absent questionnaire is not confused with "
            "one answered with zeros.")
        rep("Evaluation is done once", "reported overall and separately for each eFST group (I-II, III-IV, V-VI, "
            "missing), together with the maximum gap between groups.",
            "reported overall and separately for each eFST group (I-II, III-IV, V-VI, missing), together with the "
            "maximum gap between the tone groups (I-II, III-IV, V-VI; 'missing' is not a tone). Within a group, "
            "macro-F1 is averaged over the categories present in it (e.g. redness_rosacea has no V-VI test case). "
            f"Every value is reported with a 95% bootstrap confidence interval [{n}], obtained by resampling the test "
            "cases with replacement 1,000 times; the intervals show how certain the results are for small groups.")
        rep("Evaluation is done once", "of the questionnaire fields hidden",
            "of the questionnaire fields hidden (each field independently, on top of the answers already missing in "
            "the data; at 100% the whole questionnaire is hidden)")


for path, lang in (("Teza_Licenta.docx", "ro"), ("Paper_Skin_Concern.docx", "en")):
    ed = DocEditor(str(ROOT / "docs" / path))
    if any("find_duplicate_images" in p.text for p in ed.doc.paragraphs):
        print(path, "already updated")
        continue
    fix(ed, lang)
    try:
        ed.save()
        print(path, "updated")
    except PermissionError:
        print(path, "LOCKED (open in Word) - not updated")
