import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "features"))
import encode_questionnaire as eq  # noqa: E402

SCHEMA = Path(__file__).resolve().parents[1] / "features" / "questionnaire_schema.yaml"


def test_missing_vs_unknown_and_no_nan(tmp_path):
    cases = pd.DataFrame({
        "case_id": ["1", "2"],
        "age_group": ["AGE_UNKNOWN", None],
        "fitzpatrick_skin_type": ["NONE_IDENTIFIED", None],
        "condition_duration": ["ONE_DAY", None],
    })
    schema = eq.load_schema(SCHEMA)
    for f in schema["fields"]:
        for col in [o["column"] for o in f.get("options", [])]:
            cases[col] = None
    cases.loc[0, "condition_symptoms_itching"] = "YES"
    out, groups = eq.encode(cases.set_index("case_id"), schema)
    eq.validate(out, groups, schema, 2)
    assert out.loc["1", "f__age_group__age_unknown"] == 1 and out.loc["1", "m__age_group"] == 0
    assert out.loc["2", "m__age_group"] == 1 and out.loc["2", "f__age_group__age_unknown"] == 0
    assert out.loc["1", "m__symptoms"] == 0 and out.loc["2", "m__symptoms"] == 1
    assert out.loc["1", "f__duration__rank"] == 1 and out.loc["2", "f__duration__rank"] == 0
