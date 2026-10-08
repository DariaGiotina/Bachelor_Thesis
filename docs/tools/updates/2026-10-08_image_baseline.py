"""Add the staged fine-tuning of the image-only baseline to thesis 5.8 and paper 3.8."""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "docs" / "tools"))
from docx_tools import DocEditor  # noqa: E402

EFF = "https://arxiv.org/abs/1905.11946"
MOB = "https://arxiv.org/abs/1905.02244"
MOB_REF = ("A. Howard, M. Sandler, G. Chu, L.-C. Chen, B. Chen, M. Tan, W. Wang, Y. Zhu, R. Pang, V. Vasudevan, "
           "Q. V. Le, H. Adam, Searching for MobileNetV3, ICCV 2019")

RO = [
    "Modelul de referință doar cu imagine (`ml/models/image_model.py`) este evaluat cu două rețele preantrenate: "
    "EfficientNet-B0 [{e}] și MobileNetV3-Large [{m}], o rețea mai mică, proiectată pentru telefoane mobile, deci "
    "relevantă pentru o aplicație mobilă. Stratul de clasificare ImageNet (1.000 de clase) este înlocuit cu unul nou, "
    "cu patru ieșiri, inițializat cu ponderi mici, astfel încât la început modelul să atribuie probabilități aproape "
    "egale celor patru categorii; inițializarea implicită a bibliotecii pornea de la scoruri foarte mari și de la o "
    "pierdere de aproximativ 4,5 în loc de circa 1,4.",
    "Rețeaua este reantrenată în trei etape (staged fine-tuning), pentru a evita uitarea catastrofală (catastrophic "
    "forgetting), adică pierderea trăsăturilor utile învățate pe ImageNet atunci când toate straturile sunt modificate "
    "brusc de gradienții mari ai unui strat de clasificare încă neantrenat. În etapa 1 se antrenează doar stratul de "
    "clasificare (rata de învățare 10⁻³), restul rețelei fiind înghețat (parametrii nu se modifică). În etapa 2 se "
    "deblochează și ultimele două blocuri ale rețelei, împreună cu stratul convoluțional final, cu o rată de învățare de "
    "10 ori mai mică decât a stratului de clasificare (3·10⁻⁴ pentru clasificator, 3·10⁻⁵ pentru rețea). În etapa 3, "
    "opțională, se antrenează toți parametrii cu o rată și mai mică (10⁻⁴, respectiv 10⁻⁵). Fiecare etapă pornește de la "
    "cel mai bun punct de control de până atunci și are propriul criteriu de oprire timpurie. Straturile de normalizare "
    "pe lot (batch normalization) care sunt înghețate rămân în modul de evaluare, astfel încât statisticile lor, "
    "calculate pe ImageNet, nu sunt suprascrise. Pentru o comparație corectă cu modelul cu chestionar, aceeași "
    "procedură în etape trebuie aplicată și modelului cu fuziune.",
]
EN = [
    "The photo-only baseline (`ml/models/image_model.py`) is evaluated with two pretrained networks: EfficientNet-B0 "
    "[{e}] and MobileNetV3-Large [{m}], a smaller network designed for mobile phones and therefore relevant to a mobile "
    "app. The ImageNet classification layer (1,000 classes) is replaced by a new four-output layer initialised with "
    "small weights, so the model starts with near-equal probabilities for the four categories; the library's default "
    "initialisation started from very large scores and a loss of about 4.5 instead of about 1.4.",
    "The network is fine-tuned in three stages to avoid catastrophic forgetting, i.e. losing useful ImageNet features "
    "when all layers are changed abruptly by the large gradients of a still untrained classification layer. Stage 1 "
    "trains only the classification layer (learning rate 1e-3) with the rest of the network frozen (its parameters do "
    "not change). Stage 2 also unfreezes the last two blocks and the final convolutional layer, at a learning rate ten "
    "times lower than the classifier's (3e-4 for the classifier, 3e-5 for the network). The optional stage 3 trains all "
    "parameters at an even lower rate (1e-4 and 1e-5). Each stage starts from the best checkpoint so far and has its own "
    "early-stopping patience. Frozen batch-normalisation layers stay in evaluation mode, so their ImageNet statistics "
    "are not overwritten. For a fair comparison with the questionnaire model, the same staged procedure must also be "
    "applied to the fusion model.",
]

for path, head, paras in (("Teza_Licenta.docx", "5.8 Modelul și fuziunea multimodală", RO),
                          ("Paper_Skin_Concern.docx", "3.8 Model and training", EN)):
    ed = DocEditor(str(ROOT / "docs" / path))
    if any("image_model.py" in p.text for p in ed.doc.paragraphs):
        print(path, "already updated")
        continue
    e = ed.add_reference("", EFF)  # already listed: returns its number
    m = ed.add_reference(MOB_REF, MOB)
    ed.append_to_section(head, [t.format(e=e, m=m) for t in paras])
    try:
        ed.save()
        print(path, "updated")
    except PermissionError:
        print(path, "LOCKED (open in Word) - not updated")
