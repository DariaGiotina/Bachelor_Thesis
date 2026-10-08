# Field mapping: SCIN raw fields to the mobile app questionnaire

The app questionnaire is not built yet (the Expo scaffold has no questionnaire screen). The app
keys below are the proposed field names, and the question wording follows the SCIN contributor
app (`scin_app_questions.csv`) so the model sees the same questions at training and at use time.
Encoding is defined in `questionnaire_schema.yaml` and applied by `encode_questionnaire.py`.

**Mask rule:** `m__<field>` = 1 when the question was not answered, 0 when it was. An explicit
"unknown" answer is a present answer (mask 0) with its own indicator column. Features of a masked
field are 0 and carry no information.

## 1. Fields used

| App key | App question (SCIN wording) | SCIN column(s) | Answer type | Encoding | Feature columns | Mask `m__...` |
|---|---|---|---|---|---|---|
| `age_group` | Age (user types an age 18-150; the app converts it to a bucket) | `age_group` | single | one-hot, 6 buckets + `age_unknown` | 7 | `age_group` |
| `body_area` | Where on your body is the issue? (select all) | `body_parts_*` (12 columns) | multi-select | multi-hot | 12 | `body_area` |
| `symptoms` | Are you experiencing any of the following with your skin issue? (select all) | `condition_symptoms_*` (8 columns) | multi-select | multi-hot | 8 | `symptoms` |
| `texture` | Describe how the affected skin area feels (select all) | `textures_*` (4 columns) | multi-select | multi-hot | 4 | `texture` |
| `duration` | For how long have you had this skin issue? | `condition_duration` | single, ordered | ordinal rank 1-8 + `unknown` | 2 | `duration` |
| `skin_type` | How does your skin react to sun exposure? | `fitzpatrick_skin_type` | single | one-hot FST1-6 + `none_identified` | 7 | `skin_type` |

Total: 40 feature columns + 6 mask columns per case (`case_id` is the index).

## 2. Value mapping

**age_group** (app age is bucketed): 18-29, 30-39, 40-49, 50-59, 60-69, 70-79 map to
`AGE_18_TO_29` ... `AGE_70_TO_79`. `AGE_UNKNOWN` = the person gave no usable age (feature
`age_unknown` = 1, mask 0). A blank cell = missing (mask 1).

**body_area** options: head or neck, arm, palm, back of hand, torso front, torso back, genitalia
or groin, buttocks, leg, top or side of foot, sole of foot, other.

**symptoms** options: concerning in appearance (`bothersome_appearance`), bleeding, increasing in
size, darkening, itching, burning, pain, none of the above (`no_relevant_experience`). "None of the
above" is an answer (mask 0), not a missing value. Flaking is recorded under texture
(`rough_or_flaky`), as in SCIN.

**texture** options: raised or bumpy, flat, rough or flaky, filled with fluid.

**duration** (rank order): 1 day = 1, less than 1 week = 2, 1-4 weeks = 3, 1-3 months = 4,
3-12 months = 5, more than 1 year = 6, more than 5 years = 7, since childhood = 8. `UNKNOWN` sets
`duration__unknown` = 1 and the rank stays 0.

**skin_type** (sun reaction): FST1 always burns, never tans; FST2 usually burns, lightly tans; FST3
sometimes burns, evenly tans; FST4 rarely burns, tans well; FST5 very rarely burns, easily tans;
FST6 never burns, always tans. `NONE_IDENTIFIED` = "None of the above".

## 3. Multi-select missingness

SCIN stores each option as a column holding `YES` or blank. A blank cell means the box was not
ticked, so a question counts as not answered only when none of its boxes is ticked. A person who
saw the question but ticked nothing cannot be told apart from one who skipped it.

## 4. Fields not encoded

| SCIN column(s) | Reason |
|---|---|
| `sex_at_birth`, `race_ethnicity_*`, `combined_race` | Sensitive; reserved for fairness analysis, not model input |
| `other_symptoms_*` | Systemic symptoms, outside the requested set |
| `related_category` | Self-described category (includes ACNE), would leak the target label |
| `dermatologist_*`, `weighted_skin_condition_label`, `monk_skin_tone_*` | Labels and annotator fields, not self-reported answers |

## 5. Observed missing rates (SCIN v1.0.0, 5,033 cases)

age_group 0.0% (1 case), body_area 18.8%, symptoms 25.1%, texture 19.0%, duration 19.8%,
skin_type 50.3% (a further 328 cases answered "none of the above").
