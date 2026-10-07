import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audit_scin  # noqa: E402


def _write_fixture(d: Path) -> None:
    pd.DataFrame({
        "case_id": ["1", "2", "3"],
        "release": ["1.0.0"] * 3,
        "age_group": ["AGE_18_TO_29", "AGE_UNKNOWN", None],
        "fitzpatrick_skin_type": ["FST2", None, "NONE_IDENTIFIED"],
        "textures_flat": ["YES", None, None],
        "textures_rough_or_flaky": [None, "YES", None],
        "image_1_path": ["a.png", "b.png", "c.png"],
        "image_2_path": ["d.png", None, None],
        "image_3_path": [None, None, None],
    }).to_csv(d / "scin_cases.csv", index=False)
    pd.DataFrame({
        "case_id": ["1", "2", "3"],
        "dermatologist_fitzpatrick_skin_type_label_1": ["FST2", "FST5", None],
        "dermatologist_fitzpatrick_skin_type_label_2": ["FST3", None, None],
        "monk_skin_tone_label_us": ["2", "8", None],
        "weighted_skin_condition_label": ["{'Eczema': 0.6, 'Acne': 0.4}", "{}", None],
    }).to_csv(d / "scin_labels.csv", index=False)


def test_audit_end_to_end(tmp_path):
    data, out = tmp_path / "data", tmp_path / "out"
    data.mkdir()
    _write_fixture(data)
    sources = tmp_path / "data_sources.csv"
    assert audit_scin.main(["--data-dir", str(data), "--out-dir", str(out), "--sources-csv", str(sources)]) == 0

    schema = json.loads((out / "scin_schema.json").read_text(encoding="utf-8"))
    assert schema["n_cases"] == 3 and schema["primary_key"] == "case_id"

    row = pd.read_csv(sources).set_index("source").loc["SCIN"]
    assert row.case_count == 3 and row.image_count == 4

    df = audit_scin.derive(audit_scin.merge(*audit_scin.load(data)))
    assert df.loc["1", "_efst"] == 3  # median(2, 3) = 2.5 -> rounded half up
    assert df.loc["2", "_efst_group"] == "V-VI"
    assert df.loc["1", "_top_condition"] == "Eczema"
    assert pd.isna(df.loc["2", "_top_condition"])

    fam = audit_scin.family_answer_rates(df).set_index("family").loc["textures"]
    assert fam.answered_cases == 2  # case 3 ticked nothing -> unanswered
    report = (out / "scin_audit_report.md").read_text(encoding="utf-8")
    assert "# SCIN metadata audit" in report
