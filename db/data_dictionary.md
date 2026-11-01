# Data dictionary (schema v1, 01.11.2026)

Single reference for the app database. Every SQL `CHECK` of `db/postgres/skincare.sql` and every `$jsonSchema` rule of `db/mongo/schema/*.json` must be written from this file alone. The tables, columns and keys are those of `docs/diagrams/skincare_eer.drawio` (27 tables in BCNF, normalization in `docs/Normalizare_bazei_de_date_Giotina.docx`).

## Conventions

- **Names:** tables and columns in English, `snake_case`, identical in the diagrams, the SQL script, the MongoDB documents and the API. MongoDB collection names are given in Task D2.2.
- **Keys:** `UUID` keys (PostgreSQL `uuid`, default `gen_random_uuid()`; BSON `binData` subtype 4 with `uuidRepresentation="standard"`), the same values in both databases. Reference data uses natural keys (`concern_code`, `zone_code`) or a small integer (`question_id`).
- **Time:** every moment is `TIMESTAMPTZ` stored in UTC (BSON `date`, always UTC). `DATE` columns are calendar days in the user's time zone (`APP_USER.time_zone`), stored in BSON as `date` at 00:00 UTC of that day. `TIME` is local wall-clock time `HH:MM` (BSON `string`).
- **Numbers:** `SMALLINT` -> BSON `int`; `DECIMAL(5,4)` -> BSON `double` (comparisons in the parity test round to 4 decimals); `BOOLEAN` -> `bool`.
- **Text:** `VARCHAR(n)` / `CHAR(n)` / `TEXT` -> BSON `string` with `maxLength` n. Codes from a value set are lower-case ASCII, except the SCIN option codes kept as in the dataset (for example `AGE_18_TO_29`).
- **Null:** "yes" means the column may be NULL (in MongoDB the field may be absent or `null`); every other column is `NOT NULL` / required.
- **Origin:** *user* (typed or chosen in the app), *ML* (returned by the ML service), *import* (Open Beauty Facts, CosIng), *curated* (reference data reviewed by the author), *system* (set by the backend).
- **GDPR class:** *special* = special-category data (health, Art. 9 GDPR: photos of skin, analysis results, questionnaire answers and anything that reveals a skin condition); *personal* = other personal data; *none* = reference data. Retention is in the last section.

## Account and security

### APP_USER

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| user_id | UUID | binData(4) | no | PK | `gen_random_uuid()` | system | personal |
| email | VARCHAR(254) | string | no | lower-cased, 3-254 chars, one `@`; UQ | | user | personal |
| password_hash | VARCHAR(255) | string | no | Argon2id hash in PHC format (`$argon2id$...`) | | system | personal |
| first_name | VARCHAR(80) | string | no | 1-80 chars, trimmed | | user | personal |
| last_name | VARCHAR(80) | string | no | 1-80 chars, trimmed | | user | personal |
| date_of_birth | DATE | date | no | age >= 18 at sign-up (the model was trained on adults 18+); not in the future | | user | personal |
| skin_type | VARCHAR(20) | string | no | value set *skin type* | | user | special |
| main_concern | VARCHAR(40) | string | no | value set *main concern* | | user | special |
| climate | VARCHAR(30) | string | no | value set *climate* | | user | personal |
| language | CHAR(2) | string | no | `ro`, `en` | `ro` | user | personal |
| time_zone | VARCHAR(64) | string | no | IANA time-zone name (for example `Europe/Bucharest`) | `Europe/Bucharest` | user | personal |
| created_at | TIMESTAMPTZ | date | no | | `now()` | system | personal |
| email_verified_at | TIMESTAMPTZ | date | yes | >= created_at; NULL until the address is verified | NULL | system | personal |
| failed_logins | SMALLINT | int | no | 0-100; reset to 0 after a successful login | 0 | system | personal |
| locked_until | TIMESTAMPTZ | date | yes | set to now + 15 min after 5 failed logins in a row | NULL | system | personal |
| deletion_requested_at | TIMESTAMPTZ | date | yes | marker of a running account deletion (Task D3.4) | NULL | system | personal |

### ONE_TIME_TOKEN

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| token_id | UUID | binData(4) | no | PK | `gen_random_uuid()` | system | personal |
| user_id | UUID | binData(4) | no | FK -> APP_USER, `ON DELETE CASCADE` | | system | personal |
| purpose | VARCHAR(20) | string | no | `email_verification`, `password_reset` | | system | personal |
| token_hash | CHAR(64) | string | no | SHA-256 of the token sent by e-mail, lower-case hex `^[0-9a-f]{64}$`; UQ | | system | personal |
| created_at | TIMESTAMPTZ | date | no | | `now()` | system | personal |
| expires_at | TIMESTAMPTZ | date | no | > created_at; created_at + 24 h (verification) or + 1 h (reset) | | system | personal |
| used_at | TIMESTAMPTZ | date | yes | created_at <= used_at <= expires_at; a used token is never accepted again | NULL | system | personal |

### CONSENT

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| consent_id | UUID | binData(4) | no | PK | `gen_random_uuid()` | system | personal |
| user_id | UUID | binData(4) | no | FK -> APP_USER, `ON DELETE CASCADE` | | system | personal |
| consent_type | VARCHAR(40) | string | no | value set *consent type* | | user | personal |
| policy_version | VARCHAR(20) | string | no | version inside its consent type, `^[0-9]+\.[0-9]+$` (for example `1.0`) | | system | personal |
| granted_at | TIMESTAMPTZ | date | no | | `now()` | system | personal |
| withdrawn_at | TIMESTAMPTZ | date | yes | >= granted_at; NULL while the consent is active | NULL | user | personal |

Rows are never updated except to set `withdrawn_at` once: granting the same consent again adds a new row, so the table is the proof of consent (Art. 7(1) GDPR).

### TOKEN_FAMILY

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| family_id | UUID | binData(4) | no | PK; one family per login (session) | `gen_random_uuid()` | system | personal |
| user_id | UUID | binData(4) | no | FK -> APP_USER, `ON DELETE CASCADE` | | system | personal |
| created_at | TIMESTAMPTZ | date | no | | `now()` | system | personal |

### REFRESH_TOKEN

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| token_id | UUID | binData(4) | no | PK | `gen_random_uuid()` | system | personal |
| family_id | UUID | binData(4) | no | FK -> TOKEN_FAMILY, `ON DELETE CASCADE` | | system | personal |
| token_hash | CHAR(64) | string | no | SHA-256, lower-case hex `^[0-9a-f]{64}$`; UQ | | system | personal |
| expires_at | TIMESTAMPTZ | date | no | issue time + 30 days | | system | personal |
| revoked | BOOLEAN | bool | no | true after rotation; presenting a revoked token revokes the whole family | false | system | personal |

At most one non-revoked token per family (rotation revokes the old token and inserts the new one in one transaction).

### REMINDER

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| reminder_id | UUID | binData(4) | no | PK | `gen_random_uuid()` | system | personal |
| user_id | UUID | binData(4) | no | FK -> APP_USER, `ON DELETE CASCADE`; UQ (user_id, period) | | system | personal |
| period | VARCHAR(2) | string | no | value set *period* | | user | personal |
| time_of_day | TIME | string `HH:MM` | no | 00:00-23:59, minute precision, local time of `APP_USER.time_zone`; AM reminders 04:00-11:59, PM 12:00-23:59 | | user | personal |
| enabled | BOOLEAN | bool | no | | true | user | personal |

## Skin analysis

### SKIN_ANALYSIS

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| analysis_id | UUID | binData(4) | no | PK | `gen_random_uuid()` | system | special |
| user_id | UUID | binData(4) | no | FK -> APP_USER, `ON DELETE CASCADE` | | system | special |
| created_at | TIMESTAMPTZ | date | no | | `now()` | system | special |
| model_version | VARCHAR(40) | string | no | `skin_concern_dinov2@` + the first 16 hex digits of the model file hash (`model_sha256` of the ML service) | | ML | none |
| status | VARCHAR(16) | string | no | value set *analysis status* | | ML | special |
| ood_score | DECIMAL(5,4) | double | yes | k-NN cosine distance of the photo to the training photos, 0-2; NULL only for a model without the out-of-scope filter | | ML | special |

### QUESTION

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| question_id | SMALLINT | int | no | PK, 1-999; also the display order | | curated | none |
| field_key | VARCHAR(40) | string | no | `^[a-z][a-z0-9_]{1,39}$`; the key used by the questionnaire encoder (`ml/features/field_mapping.md`); UQ | | curated | none |
| text | VARCHAR(255) | string | no | question shown in the app (English, SCIN wording; the app translates it) | | curated | none |
| answer_type | VARCHAR(20) | string | no | value set *answer type* | | curated | none |

### QUESTION_OPTION

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| question_id | SMALLINT | int | no | FK -> QUESTION, `ON DELETE CASCADE`; PK part | | curated | none |
| option_value | VARCHAR(60) | string | no | `^[A-Za-z0-9_]{1,60}$` (SCIN codes kept as in the dataset); PK part | | curated | none |
| label | VARCHAR(120) | string | no | text shown for the option | | curated | none |
| position | SMALLINT | int | no | 1-99; UQ (question_id, position); for `ordinal` questions it is the rank, except the explicit "unknown" option, which comes last | | curated | none |
| is_red_flag | BOOLEAN | bool | no | true = the app shows the "see a doctor" message whatever the model says | false | curated | none |

### ANSWER

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| analysis_id | UUID | binData(4) | no | FK -> SKIN_ANALYSIS, `ON DELETE CASCADE` | | system | special |
| question_id | SMALLINT | int | no | FK (question_id, option_value) -> QUESTION_OPTION, `ON DELETE RESTRICT` | | user | special |
| option_value | VARCHAR(60) | string | no | an option of that question | | user | special |

PK (analysis_id, question_id, option_value). One row per ticked option; a skipped question has no row. For `single` and `ordinal` questions the API accepts at most one option.

### FACE_ZONE

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| zone_code | VARCHAR(20) | string | no | value set *face zone*; PK | | curated | none |
| zone_name | VARCHAR(40) | string | no | display name; UQ | | curated | none |

### ZONE_ASSESSMENT

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| analysis_id | UUID | binData(4) | no | FK -> SKIN_ANALYSIS, `ON DELETE CASCADE`; PK part | | system | special |
| zone_code | VARCHAR(20) | string | no | FK -> FACE_ZONE, `ON DELETE RESTRICT`; PK part | | ML | special |
| finding | VARCHAR(80) | string | no | short description of what was seen (for example "enlarged pores") | | ML | special |
| severity | VARCHAR(20) | string | no | value set *severity* | | ML | special |

Stretch goal (multi-region face chart): the table may stay empty in the MVP.

### SKIN_CONCERN

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| concern_code | VARCHAR(30) | string | no | value set *model category*; PK | | curated | none |
| name | VARCHAR(60) | string | no | display name; UQ | | curated | none |
| description | TEXT | string | no | plain-language text, informational, never a diagnosis; at most 1,000 chars | | curated | none |

### PREDICTION

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| analysis_id | UUID | binData(4) | no | FK -> SKIN_ANALYSIS, `ON DELETE CASCADE`; PK part | | system | special |
| concern_code | VARCHAR(30) | string | no | FK -> SKIN_CONCERN, `ON DELETE RESTRICT`; PK part | | ML | special |
| probability | DECIMAL(5,4) | double | no | 0-1 (calibrated) | | ML | special |

Every analysis has one row per model category (4 rows), and the probabilities add up to 1 within 0.001 (checked by the backend and by the tests, not by a constraint).

## Photos (specialization of PHOTO)

### PHOTO

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| photo_id | UUID | binData(4) | no | PK | `gen_random_uuid()` | system | special |
| object_key | VARCHAR(255) | string | no | random key in the EU object store, `^photos/[0-9a-f-]{36}$`; UQ; no file name, user or type inside it | | system | special |
| content_type | VARCHAR(40) | string | no | value set *photo content type* | | system | special |
| captured_at | TIMESTAMPTZ | date | no | not in the future | `now()` | system | special |
| photo_kind | VARCHAR(8) | string | no | `ANALYSIS`, `PROGRESS` | | system | special |

Disjoint and total: a trigger checks that the subclass row matches `photo_kind`, a deferred constraint trigger checks at commit that every PHOTO has its subclass row. In MongoDB both kinds live in one collection with `kind` and a `oneOf` validator.

### ANALYSIS_PHOTO

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| photo_id | UUID | binData(4) | no | PK, FK -> PHOTO, `ON DELETE CASCADE` | | system | special |
| analysis_id | UUID | binData(4) | no | FK -> SKIN_ANALYSIS, `ON DELETE CASCADE`; at most 3 photos per analysis | | system | special |
| shot_type | VARCHAR(20) | string | no | value set *shot type* | | user | special |
| heatmap_key | VARCHAR(255) | string | yes | Grad-CAM image key `^heatmaps/[0-9a-f-]{36}$`; unique when present | NULL | ML | special |

### PROGRESS_PHOTO

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| photo_id | UUID | binData(4) | no | PK, FK -> PHOTO, `ON DELETE CASCADE` | | system | special |
| log_id | UUID | binData(4) | no | FK -> DAILY_LOG, `ON DELETE CASCADE`; UQ (one photo per log day) | | system | special |
| caption | VARCHAR(140) | string | yes | | NULL | user | special |

## Products, routines and the daily log

### PRODUCT

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| product_id | UUID | binData(4) | no | PK | `gen_random_uuid()` | system | none |
| barcode | VARCHAR(14) | string | yes | GTIN digits `^[0-9]{8,14}$` (EAN-8, UPC-A, EAN-13, GTIN-14); unique when present | NULL | import | none |
| name | VARCHAR(160) | string | no | | | import | none |
| brand | VARCHAR(80) | string | no | | | import | none |
| category | VARCHAR(40) | string | no | value set *product category* | | curated | none |
| size | VARCHAR(20) | string | yes | quantity as printed (for example `150 ml`) | NULL | import | none |
| source | VARCHAR(40) | string | no | value set *product source* | | system | none |

### INGREDIENT

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| ingredient_id | UUID | binData(4) | no | PK | `gen_random_uuid()` | system | none |
| inci_name | VARCHAR(160) | string | no | INCI name in upper case as in CosIng (for example `NIACINAMIDE`); UQ (case-insensitive) | | import | none |
| plain_meaning | VARCHAR(255) | string | no | own plain-language explanation | | curated | none |
| score | SMALLINT | int | no | 0-100, higher = fewer reasons for caution; band in *Derived values* | | curated | none |

### PRODUCT_INGREDIENT

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| product_id | UUID | binData(4) | no | FK -> PRODUCT, `ON DELETE CASCADE`; PK part | | import | none |
| ingredient_id | UUID | binData(4) | no | FK -> INGREDIENT, `ON DELETE RESTRICT`; PK part | | import | none |
| position | SMALLINT | int | no | 1-200, order on the INCI list; UQ (product_id, position) | | import | none |

### INGREDIENT_FUNCTION and INGREDIENT_FLAG

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| INGREDIENT_FUNCTION.ingredient_id | UUID | binData(4) | no | FK -> INGREDIENT, `ON DELETE CASCADE`; PK part | | import | none |
| INGREDIENT_FUNCTION.function | VARCHAR(30) | string | no | value set *ingredient function*; PK part | | import | none |
| INGREDIENT_FLAG.ingredient_id | UUID | binData(4) | no | FK -> INGREDIENT, `ON DELETE CASCADE`; PK part | | curated | none |
| INGREDIENT_FLAG.flag | VARCHAR(30) | string | no | value set *ingredient flag*; PK part | | curated | none |

### ROUTINE

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| routine_id | UUID | binData(4) | no | PK | `gen_random_uuid()` | system | personal |
| user_id | UUID | binData(4) | no | FK -> APP_USER, `ON DELETE CASCADE` | | system | personal |
| period | VARCHAR(2) | string | no | value set *period* | | user | personal |
| complexity_level | VARCHAR(12) | string | no | value set *routine complexity* | | user | personal |
| created_at | TIMESTAMPTZ | date | no | | `now()` | system | personal |

The current routine of a period is the latest one (`created_at`); older routines are kept as history.

### ROUTINE_SOURCE

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| routine_id | UUID | binData(4) | no | PK, FK -> ROUTINE, `ON DELETE CASCADE` | | system | special |
| analysis_id | UUID | binData(4) | no | FK -> SKIN_ANALYSIS, `ON DELETE CASCADE`; same user as the routine (checked by the data layer) | | system | special |

### ROUTINE_STEP

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| routine_id | UUID | binData(4) | no | FK -> ROUTINE, `ON DELETE CASCADE`; PK part | | system | personal |
| step_no | SMALLINT | int | no | 1-12, consecutive inside a routine; PK part | | system | personal |
| product_id | UUID | binData(4) | yes | FK -> PRODUCT, `ON DELETE SET NULL`; NULL = no product chosen yet | NULL | user | personal |
| category | VARCHAR(30) | string | no | value set *step category* | | system | personal |
| instruction | VARCHAR(255) | string | no | | | system | personal |
| duration_sec | SMALLINT | int | no | 5-900 | | system | personal |

### DAILY_LOG

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| log_id | UUID | binData(4) | no | PK | `gen_random_uuid()` | system | personal |
| user_id | UUID | binData(4) | no | FK -> APP_USER, `ON DELETE CASCADE`; UQ (user_id, log_date) | | system | personal |
| log_date | DATE | date | no | local day of the user; not after today | | user | personal |
| notes | TEXT | string | yes | at most 2,000 chars; free text may describe the skin, so it is handled as special-category data | NULL | user | special |

### PRODUCT_USE

| Column | PostgreSQL | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|
| log_id | UUID | binData(4) | no | FK -> DAILY_LOG, `ON DELETE CASCADE`; PK part | | system | personal |
| product_id | UUID | binData(4) | no | FK -> PRODUCT, `ON DELETE RESTRICT`; PK part | | user | personal |
| period | VARCHAR(2) | string | no | value set *period*; PK part | | user | personal |
| used_at | TIMESTAMPTZ | date | no | moment the product was ticked | `now()` | system | personal |

## Value sets

| Value set | Values | Used by |
|---|---|---|
| skin type | `normal`, `dry`, `oily`, `combination`, `sensitive` | APP_USER.skin_type |
| main concern | `acne`, `redness`, `dryness`, `oiliness_pores`, `sensitivity`, `hyperpigmentation`, `signs_of_aging`, `none` | APP_USER.main_concern (self-reported goal, wider than the model categories) |
| climate | `temperate`, `humid`, `dry`, `cold` | APP_USER.climate |
| language | `ro`, `en` | APP_USER.language |
| consent type | `privacy_policy`, `photo_processing`, `health_data`, `reminders` | CONSENT.consent_type |
| one-time token purpose | `email_verification`, `password_reset` | ONE_TIME_TOKEN.purpose |
| period | `AM`, `PM` | REMINDER, ROUTINE, PRODUCT_USE |
| analysis status | `answered` (category shown), `uncertain` (confidence below the threshold: "see a professional"), `unusual_photo` (the out-of-scope filter flagged the photo) | SKIN_ANALYSIS.status, as returned by `ml/serving.py` |
| model category | `acne`, `eczema_dermatitis`, `redness_rosacea`, `normal_other` (the order of the exported model) | SKIN_CONCERN.concern_code |
| answer type | `single`, `multi`, `ordinal` | QUESTION.answer_type |
| face zone | `forehead`, `nose`, `left_cheek`, `right_cheek`, `chin`, `jawline` | FACE_ZONE.zone_code |
| severity | `mild`, `moderate`, `pronounced` | ZONE_ASSESSMENT.severity |
| photo kind | `ANALYSIS`, `PROGRESS` | PHOTO.photo_kind |
| photo content type | `image/jpeg`, `image/png`, `image/webp` (the formats the ML service accepts) | PHOTO.content_type |
| shot type | `front`, `left`, `right` | ANALYSIS_PHOTO.shot_type |
| routine complexity | `basic` (about 3 steps), `intermediate` (about 5), `advanced` (7 or more) | ROUTINE.complexity_level |
| step category | `cleansing`, `prep`, `treatment`, `hydration`, `protection` | ROUTINE_STEP.category |
| product category | `cleanser`, `toner`, `serum`, `moisturizer`, `sunscreen`, `exfoliant`, `mask`, `eye_care`, `other` | PRODUCT.category |
| product source | `curated` (entered and reviewed by the author), `openbeautyfacts` (imported from Open Beauty Facts) | PRODUCT.source |
| ingredient function | CosIng function names in lower case with `_`: `abrasive`, `absorbent`, `antimicrobial`, `antioxidant`, `antiperspirant`, `antistatic`, `astringent`, `binding`, `bleaching`, `buffering`, `chelating`, `cleansing`, `colorant`, `denaturant`, `deodorant`, `emollient`, `emulsifying`, `emulsion_stabilising`, `exfoliating`, `film_forming`, `foam_boosting`, `gel_forming`, `hair_conditioning`, `humectant`, `keratolytic`, `masking`, `moisturising`, `opacifying`, `perfuming`, `plasticiser`, `preservative`, `refreshing`, `skin_conditioning`, `skin_protecting`, `smoothing`, `solvent`, `soothing`, `surfactant`, `tonic`, `uv_absorber`, `uv_filter`, `viscosity_controlling` | INGREDIENT_FUNCTION.function |
| ingredient flag | `fragrance` (perfume, parfum), `fragrance_allergen` (one of the allergens that EU labelling rules name), `essential_oil`, `drying_alcohol` (alcohol denat. and similar), `exfoliating_acid` (AHA, BHA), `retinoid`, `comedogenic`, `formaldehyde_releaser` | INGREDIENT_FLAG.flag |

Questionnaire codes (QUESTION_OPTION.option_value) come from `ml/features/questionnaire_schema.yaml`: `age_group`, `body_area`, `symptoms`, `texture`, `duration` (ordinal, ranks 1-8) and the Fitzpatrick sun-reaction question (field key `skin_type`, a different thing from the cosmetic `APP_USER.skin_type`), plus the red-flag question `lesion_change`. Options marked `is_red_flag`: symptoms `bleeding`, `increasing_size`, `darkening`, `pain`; lesion_change `yes`.

## Derived values (computed, never stored)

| Derived attribute | Rule | SQL | MongoDB |
|---|---|---|---|
| APP_USER.age_range | age in whole years from `date_of_birth` to today, banded `18-19`, `20-29`, `30-39`, `40-49`, `50-59`, `60+` | view `v_user_profile` | `$dateDiff` in an aggregation |
| SKIN_ANALYSIS.overall_confidence | largest `probability` of the analysis | view `v_analysis_result` | computed from the embedded predictions |
| top concern | `concern_code` with the largest probability, shown only when `status = 'answered'` | view `v_analysis_result` | idem |
| PREDICTION.rank | 1 for the largest probability of the analysis, ties broken by `concern_code` | view `v_prediction_rank` (window function) | `$sortArray` / `$setWindowFields` |
| ingredient band | `safe` if score >= 70, `caution` if 40-69, `irritant` if < 40 (the three labels of the product screen) | expression in `v_product_safety` | computed field |
| PRODUCT.safety_score | weighted mean of the ingredient scores with weight 1/position (earlier INCI positions mean higher concentration), rounded to an integer 0-100; NULL when the product has no ingredient list | view `v_product_safety` | computed pattern: stored copy refreshed when an ingredient changes (Task D2.2) |
| product flag summary | number of ingredients per band and the distinct flags of its ingredients | view `v_product_safety` | idem |
| ROUTINE.total_duration | sum of `duration_sec` of its steps | query / view | `$sum` over the embedded steps |

The safety score is an informational summary of a curated list, not a safety assessment of the product; the app says so next to the number.

## Retention and erasure

| Data | Kept | Removed by |
|---|---|---|
| Account (APP_USER and everything owned by the user) | until the user deletes the account | account deletion: all rows owned by the user (`ON DELETE CASCADE`), then the photo objects in the object store; marker `deletion_requested_at` makes the job resumable |
| Photos and analyses (special category) | until the user deletes them or the account | the same, or deletion of a single analysis / photo |
| CONSENT | while the account exists (proof of consent) | account deletion |
| REFRESH_TOKEN, TOKEN_FAMILY | until `expires_at` (30 days) | TTL index in MongoDB; scheduled `DELETE` in PostgreSQL; logout revokes the family |
| ONE_TIME_TOKEN | until `expires_at` (1 h or 24 h) | TTL index / scheduled `DELETE` |
| Backups | 4 daily Atlas snapshots | data of a deleted account disappears from the backups within 4 days |
| Reference data (questions, categories, zones, products, ingredients) | no personal data | curated updates |
