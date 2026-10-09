# Why the questionnaire does not improve the photo model (seeds 0-9, test)

## A. Complementarity (photo-only vs questionnaire-only predictions)

| Quantity | Mean ± sd |
|---|---|
| n | 270.800 ± 1.033 |
| acc_photo | 0.564 ± 0.026 |
| acc_questionnaire | 0.482 ± 0.040 |
| p_q_right_if_photo_wrong | 0.426 ± 0.045 |
| p_q_right_if_photo_right | 0.526 ± 0.062 |
| oracle_either_right | 0.749 ± 0.026 |
| same_prediction | 0.445 ± 0.051 |

If errors were independent, P(questionnaire right | photo wrong) would equal the questionnaire's overall accuracy.

## B. Which questions carry the signal (questionnaire-only model)

| Question | Macro-F1 drop when hidden | Macro-F1 with only this question | Answered share |
|---|---|---|---|
| (none: all hidden) | +0.242 ± 0.063 | 0.138 | nan |
| body_area | +0.125 ± 0.057 | 0.240 | 0.83 |
| duration | +0.057 ± 0.065 | 0.117 | 0.83 |
| symptoms | +0.053 ± 0.043 | 0.207 | 0.77 |
| texture | +0.043 ± 0.043 | 0.172 | 0.83 |
| skin_type | +0.012 ± 0.022 | 0.172 | 0.55 |
| age_group | +0.012 ± 0.037 | 0.154 | 1.00 |

## C. Can the photo model see the answers? (AUROC of the answer from the photo features)

| Answer | AUROC | Share yes | Test cases |
|---|---|---|---|
| age: 50 or older | 0.699 | 0.21 | 124 |
| body_area: arm | 0.688 | 0.47 | 225 |
| body_area: palm | 0.644 | 0.06 | 225 |
| body_area: head_or_neck | 0.628 | 0.16 | 225 |
| body_area: buttocks | 0.617 | 0.10 | 225 |
| body_area: torso_back | 0.604 | 0.16 | 225 |
| body_area: leg | 0.601 | 0.41 | 225 |
| body_area: back_of_hand | 0.601 | 0.15 | 225 |
| body_area: genitalia_or_groin | 0.594 | 0.05 | 225 |
| self-reported skin type: V-VI | 0.589 | 0.17 | 131 |
| body_area: other | 0.589 | 0.13 | 225 |
| body_area: torso_front | 0.581 | 0.19 | 225 |
| body_area: foot_top_or_side | 0.578 | 0.10 | 225 |
| symptoms: burning | 0.573 | 0.27 | 208 |
| body_area: foot_sole | 0.573 | 0.03 | 225 |
| symptoms: darkening | 0.568 | 0.09 | 208 |
| symptoms: itching | 0.560 | 0.78 | 208 |
| symptoms: pain | 0.558 | 0.18 | 208 |
| duration: longer than median | 0.556 | 0.47 | 221 |
| texture: fluid_filled | 0.552 | 0.15 | 226 |
| symptoms: no_relevant_experience | 0.544 | 0.06 | 208 |
| symptoms: bleeding | 0.540 | 0.06 | 208 |
| texture: rough_or_flaky | 0.534 | 0.28 | 226 |
| texture: raised_or_bumpy | 0.512 | 0.76 | 226 |
| symptoms: bothersome_appearance | 0.511 | 0.39 | 208 |
| symptoms: increasing_size | 0.505 | 0.27 | 208 |
| texture: flat | 0.499 | 0.15 | 226 |

AUROC 0.5 = the answer is not recoverable from the photo features; 1.0 = fully recoverable.
