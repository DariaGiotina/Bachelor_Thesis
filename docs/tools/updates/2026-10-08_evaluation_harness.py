"""Add the evaluation harness (calibration, risk-coverage, worst group, case bootstrap) to thesis 5.10 / paper 3.9."""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocEditor  # noqa: E402

GUO = ("https://arxiv.org/abs/1706.04599",
       "C. Guo, G. Pleiss, Y. Sun, K. Q. Weinberger, On Calibration of Modern Neural Networks, ICML 2017")
GEIF = ("https://arxiv.org/abs/1705.08500",
        "Y. Geifman, R. El-Yaniv, Selective Classification for Deep Neural Networks, NeurIPS 2017")
SAG = ("https://arxiv.org/abs/1911.08731",
       "S. Sagawa, P. W. Koh, T. B. Hashimoto, P. Liang, Distributionally Robust Neural Networks for Group Shifts, "
       "ICLR 2020")
BOOT = "https://doi.org/10.1201/9780429246593"

RO = [
    "Evaluarea este realizată de scriptul `ml/evaluate.py`, care citește un fișier standard de predicții "
    "(`predictions.csv`, câte un rând pe caz, cu categoria reală, categoria prezisă, încrederea, eFST, eMST, seed-ul și "
    "proporția de răspunsuri ascunse). Pe lângă macro-F1 și acuratețea echilibrată, se raportează precizia, recall-ul și "
    "F1 pentru fiecare categorie. Precizia arată ce proporție dintre cazurile atribuite unei categorii aparțin cu adevărat "
    "ei, iar recall-ul ce proporție dintre cazurile unei categorii au fost găsite.",
    "Calibrarea arată dacă încrederea modelului corespunde realității: un model bine calibrat care afirmă 80% încredere "
    "are dreptate în aproximativ 80% din cazuri. Încrederea este probabilitatea maximă dată de model unei categorii. Se "
    "măsoară prin eroarea de calibrare așteptată (Expected Calibration Error, ECE) [{guo}]: predicțiile sunt împărțite în "
    "15 intervale egale după încredere, iar ECE este media ponderată a diferenței dintre încrederea medie și acuratețea "
    "din fiecare interval. Pentru o aplicație informativă contează și curba risc-acoperire (risk-coverage) [{geif}]: dacă "
    "aplicația răspunde doar când încrederea depășește un prag și altfel recomandă consultarea unui specialist, curba arată "
    "acuratețea obținută pentru fiecare proporție de cazuri la care răspunde (acoperire). Aria de sub curba riscului "
    "(AURC) rezumă curba într-un singur număr; o valoare mai mică este mai bună.",
    "Echitatea este raportată pe ambele scale de ton, eFST (I–II, III–IV, V–VI) și eMST (1–3, 4–6, 7–10). Pentru fiecare "
    "scală se identifică grupul cel mai defavorizat (worst group) [{sag}], adică grupul de ton cu cel mai mic macro-F1, "
    "împreună cu diferența față de grupul cel mai bun. Doar grupurile cu cel puțin 20 de cazuri pot fi desemnate astfel, "
    "deoarece pe grupuri mai mici estimarea este prea nesigură; grupurile excluse sunt menționate explicit. Intervalele "
    "de încredere bootstrap [{boot}] reeșantionează cazuri (`case_id`), nu rânduri: toate rândurile unui caz sunt păstrate "
    "împreună, astfel încât observațiile aceluiași caz nu sunt tratate ca independente. Rezultatele celor cinci seed-uri "
    "sunt rezumate prin medie, abatere standard, minim și maxim.",
]
EN = [
    "Evaluation is performed by `ml/evaluate.py`, which reads a standard predictions file (`predictions.csv`, one row "
    "per case with the true category, the predicted category, the confidence, eFST, eMST, the seed and the share of hidden "
    "answers). Besides macro-F1 and balanced accuracy, it reports precision, recall and F1 for every category. Precision "
    "is the share of cases assigned to a category that truly belong to it; recall is the share of a category's cases "
    "that were found.",
    "Calibration shows whether the model's confidence matches reality: a well-calibrated model that states 80% confidence "
    "is right in about 80% of cases. Confidence is the highest probability the model gives to any category. It is measured "
    "by the Expected Calibration Error (ECE) [{guo}]: predictions are split into 15 equal-width confidence bins, and ECE "
    "is the size-weighted mean difference between mean confidence and accuracy in each bin. For an informational app the "
    "risk-coverage curve [{geif}] also matters: if the app answers only above a confidence threshold and otherwise "
    "recommends seeing a professional, the curve gives the accuracy for each share of cases it answers (coverage). The "
    "area under the risk curve (AURC) summarises it in one number; lower is better.",
    "Fairness is reported on both tone scales, eFST (I-II, III-IV, V-VI) and eMST (1-3, 4-6, 7-10). For each scale we "
    "identify the worst group [{sag}], the tone group with the lowest macro-F1, and its gap to the best group. Only "
    "groups with at least 20 cases are eligible, because estimates on smaller groups are too uncertain; excluded groups "
    "are listed explicitly. Bootstrap confidence intervals [{boot}] resample cases (`case_id`), not rows: all rows of a "
    "case stay together, so observations of the same case are not treated as independent. Results over the five seeds are "
    "summarised by mean, standard deviation, minimum and maximum.",
]

for path, head, paras in (("Teza_Licenta.docx", "5.10 Protocolul de evaluare", RO),
                          ("Paper_Skin_Concern.docx", "3.9 Evaluation protocol", EN)):
    ed = DocEditor(str(ROOT / "docs" / path))
    if any("evaluate.py" in p.text for p in ed.doc.paragraphs):
        print(path, "already updated")
        continue
    n = {k: ed.add_reference(t, u) for k, (u, t) in {"guo": GUO, "geif": GEIF, "sag": SAG}.items()}
    n["boot"] = ed.add_reference("", BOOT)  # already listed
    ed.append_to_section(head, [t.format(**n) for t in paras])
    try:
        ed.save()
        print(path, "updated")
    except PermissionError:
        print(path, "LOCKED (open in Word) - not updated")
