"""Why the questionnaire does not help: diagnostics in thesis 8.5 / paper 4.5; correct the redundancy hypothesis in 8.3 / 4.3."""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocEditor  # noqa: E402

WARD = ("https://arxiv.org/abs/2402.18545",
        "A. Ward, J. Li, J. Wang et al., Crowdsourcing Dermatology Images with Google Search Ads: Creating a "
        "Real-World Skin Condition Dataset, JAMA Network Open 2024")
AUROC = ("https://doi.org/10.1016/j.patrec.2005.10.010",
         "T. Fawcett, An introduction to ROC analysis, Pattern Recognition Letters 27(8), 2006")

OLD_RO = ("O explicație posibilă este că o parte din informația chestionarului (de exemplu zona corpului sau aspectul "
          "leziunii) este deja vizibilă în fotografie.")
NEW_RO = ("O primă ipoteză, că informația chestionarului (de exemplu zona corpului sau aspectul leziunii) ar fi deja "
          "vizibilă în fotografie, a fost testată în secțiunea 8.5 și nu s-a confirmat.")
OLD_EN = ("A possible explanation is that part of the questionnaire's information (e.g. body area or lesion texture) is "
          "already visible in the photo.")
NEW_EN = ("A first hypothesis, that the questionnaire's information (e.g. body area or lesion texture) is already "
          "visible in the photo, was tested in Section 4.5 and not supported.")

RO = [
    "Rezultatul este surprinzător, deoarece în SCIN dermatologii au văzut atât fotografiile, cât și răspunsurile la "
    "chestionar atunci când au stabilit etichetele, iar încrederea lor a crescut cu numărul de răspunsuri disponibile "
    "[{ward}]. Pentru a înțelege de ce modelele nu profită de chestionar, scriptul "
    "`ml/analysis/questionnaire_diagnostics.py` face trei verificări pe modelele deja antrenate (zece seed-uri, fără "
    "reantrenare); rezultatele sunt în `ml/results/e1/diagnostics/`.",
    "(1) Poate modelul cu imagine să „vadă” răspunsurile? Pe trăsăturile interne ale rețelei antrenate pe fotografii se "
    "antrenează o regresie logistică ce prezice fiecare răspuns, iar calitatea predicției se măsoară prin AUROC [{auroc}] "
    "(aria de sub curba ROC: 0,5 înseamnă ghicire la întâmplare, 1 înseamnă predicție perfectă). Valorile sunt între "
    "0,50 și 0,70: zona corpului 0,57–0,69, simptomele 0,51–0,57, textura 0,50–0,55, durata 0,56. Fotografiile din SCIN "
    "sunt în mare parte prim-planuri, deci nici zona corpului nu se vede bine. Chestionarul conține așadar informație pe "
    "care modelul cu imagine nu o are; ipoteza redundanței nu se confirmă.",
    "(2) Greșesc cele două modele pe aceleași cazuri? Dacă erorile ar fi independente, modelul doar cu chestionar ar avea "
    "dreptate la cazurile greșite de fotografie la fel de des ca în general (48,2%). În realitate are dreptate doar în "
    "42,6% dintre ele, față de 52,6% la cazurile pe care fotografia le rezolvă corect. Erorile sunt deci corelate: "
    "cazurile grele sunt grele pentru ambele modele, ceea ce indică imagini ambigue și etichete zgomotoase, nu lipsă de "
    "informație. Ar exista totuși loc de câștig: un „oracol” care ar alege mereu modelul corect ar atinge acuratețea "
    "0,749 față de 0,564 pentru fotografie, dar nimic din datele de intrare nu spune când să ai încredere în chestionar; "
    "ansamblul, care a încercat exact acest lucru cu o pondere aleasă pe validare, nu a reușit.",
    "(3) Ce întrebări contează? Ascunzând câte o întrebare din modelul doar cu chestionar, cea mai mare pierdere apare "
    "la zona corpului (macro-F1 scade cu 0,125), urmată de durată (0,057), simptome (0,053) și textură (0,043); tipul "
    "de piele declarat și vârsta aproape nu contează (0,012 fiecare). Semnalul chestionarului este, în ansamblu, slab "
    "(macro-F1 0,381 față de 0,519 pentru fotografie) și concentrat într-o singură întrebare.",
    "Explicația care rezultă este următoarea: chestionarul aduce informație diferită de fotografie, dar slabă, iar "
    "partea ei utilă se suprapune în mare parte cu cazurile pe care fotografia le rezolvă deja. Partea cu adevărat "
    "complementară este mică și zgomotoasă, iar circa 1.270 de cazuri de antrenare, cu etichete date în majoritate de "
    "un singur dermatolog, nu ajung pentru ca un model să învețe în mod fiabil când să se bazeze pe ea. Acest lucru "
    "sugerează direcții concrete pentru o aplicație: întrebările despre zona corpului și durată sunt cele care merită "
    "păstrate, iar un set de date mai mare sau etichete mai sigure ar fi necesare pentru a obține un câștig măsurabil.",
]
EN = [
    "The result is surprising, because in SCIN the dermatologists saw both the photos and the questionnaire answers when "
    "they assigned labels, and their confidence increased with the number of available answers [{ward}]. To understand "
    "why the models do not benefit from the questionnaire, `ml/analysis/questionnaire_diagnostics.py` runs three checks "
    "on the already trained models (ten seeds, no retraining); results are in `ml/results/e1/diagnostics/`.",
    "(1) Can the photo model 'see' the answers? A logistic regression on the internal features of the network trained on "
    "photos predicts each answer, and prediction quality is measured by the AUROC [{auroc}] (area under the ROC curve: "
    "0.5 means random guessing, 1 means perfect prediction). Values range from 0.50 to 0.70: body area 0.57-0.69, "
    "symptoms 0.51-0.57, texture 0.50-0.55, duration 0.56. SCIN photos are mostly close-ups, so even the body area is "
    "hard to see. The questionnaire therefore holds information the photo model lacks; the redundancy hypothesis is not "
    "supported.",
    "(2) Do the two models fail on the same cases? If errors were independent, the questionnaire-only model would be "
    "right on the photo's mistakes as often as overall (48.2%). In fact it is right on only 42.6% of them, versus 52.6% "
    "on the cases the photo gets right. Errors are therefore correlated: hard cases are hard for both models, which "
    "points to ambiguous images and noisy labels rather than missing information. There would still be room for gain: an "
    "'oracle' that always picks the right model would reach an accuracy of 0.749 versus 0.564 for the photo, but nothing "
    "in the inputs tells when to trust the questionnaire; the ensemble, which tried exactly that with a weight chosen on "
    "validation, did not succeed.",
    "(3) Which questions matter? Hiding one question at a time from the questionnaire-only model, the largest loss comes "
    "from body area (macro-F1 drops by 0.125), followed by duration (0.057), symptoms (0.053) and texture (0.043); the "
    "self-reported skin type and age hardly matter (0.012 each). Overall the questionnaire's signal is weak (macro-F1 "
    "0.381 versus 0.519 for the photo) and concentrated in a single question.",
    "The resulting explanation is: the questionnaire carries information that differs from the photo but is weak, and its "
    "useful part largely overlaps with the cases the photo already solves. The truly complementary part is small and "
    "noisy, and about 1,270 training cases, mostly labelled by a single dermatologist, are not enough for a model to "
    "learn reliably when to rely on it. This suggests concrete directions for an app: the body-area and duration "
    "questions are the ones worth keeping, and a larger dataset or more reliable labels would be needed to obtain a "
    "measurable gain.",
]

for path, head, next_head, paras, old, new in (
        ("Teza_Licenta.docx", "8.5 De ce nu ajută chestionarul?", "Capitolul 9. Concluzii și direcții viitoare", RO,
         OLD_RO, NEW_RO),
        ("Paper_Skin_Concern.docx", "4.5 Why does the questionnaire not help?", "5. Discussion", EN, OLD_EN, NEW_EN)):
    ed = DocEditor(str(ROOT / "docs" / path))
    if ed.has_heading(head):
        print(path, "already updated")
        continue
    n = {"ward": ed.add_reference(WARD[1], WARD[0]), "auroc": ed.add_reference(AUROC[1], AUROC[0])}
    p = next(p for p in ed.doc.paragraphs if old in p.text)
    DocEditor._set_text(p, p.text.replace(old, new))
    anchor = ed.heading(next_head)
    ed.heading_before(anchor, head, 2)
    for t in paras:
        ed.body_paragraph_before(anchor, t.format(**n))
    try:
        ed.save()
        print(path, "updated")
    except PermissionError:
        print(path, "LOCKED (open in Word) - not updated")
