# Data dictionary (schema v1, 01.11.2026; Oracle column added 21.11.2026)

Single reference for the app database. Every SQL `CHECK` of `db/oracle/skincare.sql` and every `$jsonSchema` rule of `db/mongo/schema/*.json` must be written from this file alone. The tables, columns and keys are those of `docs/diagrams/skincare_eer.drawio` (27 tables in BCNF, normalization in `docs/Normalizare_bazei_de_date_Giotina.docx`). The relational reference implementation runs on Oracle (Oracle AI Database 26ai Free); the PostgreSQL column stays as the portable SQL type of the design.

## Conventions

- **Names:** tables and columns in English, `snake_case`, identical in the diagrams, the SQL script, the MongoDB documents and the API. MongoDB collection names and the place of every table are in *MongoDB mapping* below.
- **Keys:** `UUID` keys (PostgreSQL `uuid`, default `gen_random_uuid()`; BSON `binData` subtype 4 with `uuidRepresentation="standard"`), the same values in both databases. Reference data uses natural keys (`concern_code`, `zone_code`) or a small integer (`question_id`).
- **Time:** every moment is `TIMESTAMPTZ` stored in UTC (BSON `date`, always UTC). `DATE` columns are calendar days in the user's time zone (`APP_USER.time_zone`), stored in BSON as `date` at 00:00 UTC of that day. `TIME` is local wall-clock time `HH:MM` (BSON `string`).
- **Numbers:** `SMALLINT` -> BSON `int`; `DECIMAL(5,4)` -> BSON `double` (comparisons in the parity test round to 4 decimals); `BOOLEAN` -> `bool`.
- **Text:** `VARCHAR(n)` / `CHAR(n)` / `TEXT` -> BSON `string` with `maxLength` n. Codes from a value set are lower-case ASCII, except the SCIN option codes kept as in the dataset (for example `AGE_18_TO_29`).
- **Null:** "yes" means the column may be NULL (in MongoDB the field may be absent or `null`); every other column is `NOT NULL` / required.
- **Origin:** *user* (typed or chosen in the app), *ML* (returned by the ML service), *import* (Open Beauty Facts, CosIng), *curated* (reference data reviewed by the author), *system* (set by the backend).
- **GDPR class:** *special* = special-category data (health, Art. 9 GDPR: photos of skin, analysis results, questionnaire answers and anything that reveals a skin condition); *personal* = other personal data; *none* = reference data. Retention is in the last section.

## Oracle mapping (Task O2, 21.11.2026)

| PostgreSQL | Oracle | Why |
|---|---|---|
| `UUID` | `CHAR(36 CHAR)`, domain `d_uuid` (lower-case `8-4-4-4-12` hex, format `CHECK`) | Oracle has no UUID type. The text form keeps the seed, the API and the SQL-MongoDB parity test (Task D3.6) on the same string, with no `RAWTOHEX` conversion in every comparison. `RAW(16)` would save 20 bytes per key, which does not matter at this size. New keys: `SYS_GUID()` formatted as `8-4-4-4-12` (column `DEFAULT`). |
| `VARCHAR(n)` | `VARCHAR2(n CHAR)` | Length in characters, not bytes, so names with diacritics (`Humectación`) fit the same limits as in PostgreSQL. |
| `CHAR(n)` | `CHAR(n CHAR)`; SHA-256 hashes use domain `d_sha256` | Same reason. |
| `TEXT` | `VARCHAR2(1000 CHAR)` (descriptions) or `VARCHAR2(2000 CHAR)` (notes) | Both have a stated maximum, so no `CLOB` is needed. |
| `SMALLINT` | `NUMBER(p)` with the precision of the range (`NUMBER(2)` for 1-99, `NUMBER(3)` for up to 999) | Oracle's `SMALLINT` is `NUMBER(38)`; the `CHECK` keeps the exact range. |
| `DECIMAL(5,4)` | `NUMBER(5,4)`; probabilities use domain `d_probability` (0-1) | Same precision as the ML service output. |
| `TIMESTAMPTZ` | `TIMESTAMP WITH TIME ZONE`, domain `d_utc_ts` (offset must be +00:00) | Every moment stays in UTC, as in MongoDB. Default `FROM_TZ(SYS_EXTRACT_UTC(SYSTIMESTAMP), 'UTC')`, which does not depend on the session time zone. |
| `DATE` | `DATE` with `CHECK (col = TRUNC(col))` | Oracle's `DATE` also stores a time of day; the check keeps it a calendar day. |
| `TIME` | `VARCHAR2(5 CHAR)` `HH:MM` with a format `CHECK` | Oracle has no time-of-day type; MongoDB stores the same string. |
| `BOOLEAN` | `BOOLEAN` | SQL type since Oracle 23ai. |
| period `AM`/`PM` | domain `d_period` | Used by three tables. |

- **Reserved words:** every name was checked against Oracle's reserved words (`V$RESERVED_WORDS` where `reserved = 'Y'`, and the list in the SQL Language Reference). Only `PRODUCT.size` collided (`SIZE` is reserved), so it became `pack_size` in every implementation and diagram. `FUNCTION` (`INGREDIENT_FUNCTION.function`) is accepted in SQL but reserved in PL/SQL, so PL/SQL code must write it as `"FUNCTION"`; `position`, `level`, `comment`, `date` and `mode` do not occur or are not reserved.
- **Referential actions:** Oracle has `ON DELETE CASCADE` and `ON DELETE SET NULL`; a foreign key without an action rejects the delete, which is the `RESTRICT` of this dictionary. There is no `ON UPDATE`, and none is needed because keys never change.
- **Specialization of PHOTO:** a trigger on each subclass checks `PHOTO.photo_kind` (disjoint). Oracle has no deferred triggers; totality comes from two deferred SQL assertions (Oracle 23.26), and the package `photo_api` writes the PHOTO row and its subclass row in one call; the application user has no `INSERT` on the three photo tables.
- **Users:** `SKINCARE` owns the schema; `SKINCARE_APP` (the backend) gets `SELECT, INSERT, UPDATE, DELETE` on the user tables and only `SELECT` on the reference tables (concerns, zones, questions, options, products, ingredients and their lists).

## MongoDB mapping (Task M2, 28.11.2026)

Terms. A *document* is one record in BSON (binary JSON): named fields whose values may be numbers, text, dates, nested documents (*subdocuments*) or *arrays* (ordered lists). A *collection* is a set of documents, the counterpart of a table, but without a fixed column list (the validators of Task M3 add one). *Embedding* stores child rows as an array or subdocument inside the parent document, so one read returns both; a *reference* stores only the key of a document in another collection, like a foreign key, and the two are read with two queries or a `$lookup` stage. The method follows the MongoDB manual: workload first, then relationships, then patterns ([data modeling](https://www.mongodb.com/docs/manual/data-modeling/), [embed or reference](https://www.mongodb.com/docs/manual/data-modeling/best-practices/)).

### Workload (D2.1)

Frequency is a rough estimate for one active user: *high* = several times per session, *medium* = once per day, *low* = a few times per month or less.

| Operation | R/W | Frequency | Entities read or written together | Collection(s) | Index used |
|---|---|---|---|---|---|
| Log in by e-mail | R + W | medium | APP_USER (hash, account status), new TOKEN_FAMILY + REFRESH_TOKEN | `users`, `refresh_tokens` | unique `users.email` |
| Refresh the access token | R + W | high | REFRESH_TOKEN, its family (revoke old, insert new in one transaction) | `refresh_tokens` | unique `token_hash`; `family_id` |
| E-mail verification / password reset | R + W | low | ONE_TIME_TOKEN, APP_USER | `one_time_tokens`, `users` | unique `token_hash` |
| Sign-up with consents | W | low | APP_USER + skin profile, CONSENT rows | `users`, `consents` | unique `users.email` |
| New analysis | W | medium | SKIN_ANALYSIS + ANSWER + PREDICTION (+ ZONE_ASSESSMENT), PHOTO + ANALYSIS_PHOTO | `skin_analyses`, `photos` | `photos.object_key` (unique) |
| History page (paginated) | R | medium | SKIN_ANALYSIS + top PREDICTION | `skin_analyses` | `{user_id: 1, created_at: -1}` |
| Analysis detail / result screen | R | medium | SKIN_ANALYSIS, ANSWER, PREDICTION, ZONE_ASSESSMENT, analysis photos, SKIN_CONCERN text | `skin_analyses`, `photos`, `skin_concerns` | `_id`; `photos {user_id, kind}` |
| Barcode lookup | R | high | PRODUCT + PRODUCT_INGREDIENT + INGREDIENT names, safety score | `products` | unique partial `barcode` |
| Product text search | R | medium | PRODUCT (name, brand) | `products` | text index on name and brand |
| Ingredient detail | R | medium | INGREDIENT + functions + flags | `ingredients` | unique `inci_name` / `_id` |
| Routine of the day | R | high | latest ROUTINE per period + ROUTINE_STEP + product name and brand | `routines` | `{user_id: 1, period: 1}` |
| Tick a product in the daily log | W | high | DAILY_LOG (created on the first tick of the day) + PRODUCT_USE | `daily_logs` | unique `{user_id: 1, log_date: 1}` (upsert) |
| Calendar month | R | medium | DAILY_LOG days of a month + ticks | `daily_logs` | `{user_id: 1, log_date: 1}` (range) |
| Progress-photo timeline | R | low | PHOTO + PROGRESS_PHOTO + log day | `photos`, `daily_logs` | `photos {user_id: 1, kind: 1}` |
| Consent check before a photo upload | R | medium | active CONSENT of type `photo_processing` | `consents` | `{user_id: 1, consent_type: 1}` |
| Data export (GDPR Art. 15/20) | R | low | everything owned by the user | all user collections | `user_id` in each |
| Account deletion | W | low | everything owned by the user, in one transaction | all user collections | `user_id` in each |

Reads dominate (about 10 reads per write); the only frequent writes are token rotation and daily-log ticks, both single-document or two-document operations.

### Collections (D2.2)

13 collections. Every table appears exactly once.

| Table | Target (collection / path) | `_id` or key inside the array | Embed or reference, and why | Upper bound (rule; seed maximum) |
|---|---|---|---|---|
| APP_USER | `users` | `_id` = user_id | collection; skin columns grouped as subdocument `skin_profile` (`skin_type`, `main_concern`, `climate`), account columns as `account_status` (`email_verified_at`, `failed_logins`, `locked_until`, `deletion_requested_at`): the composite attributes of the EER come back | - |
| REMINDER | `users.reminders[]` | `period` (unique in the array) | embed: read with the profile, at most one per period | 2 (one per period; 2) |
| CONSENT | `consents` | `_id` = consent_id | reference (`user_id`): append-only proof written at different times, grows without a bound | - (4 per user in the seed) |
| ONE_TIME_TOKEN | `one_time_tokens` | `_id` = token_id | reference: looked up by hash without the user, deleted by a TTL index | - |
| TOKEN_FAMILY | `refresh_tokens.family_id` (+ `family_created_at`) | distinct `family_id` | folded into the token documents: a family is created together with its first token, so it is never empty (true for all 7 seed families) | - |
| REFRESH_TOKEN | `refresh_tokens` | `_id` = token_id | collection: looked up by hash, deleted by a TTL index; one family can rotate many times in 30 days | - (2 per family in the seed) |
| SKIN_ANALYSIS | `skin_analyses` | `_id` = analysis_id | collection, `user_id` reference | - (3 per user in the seed) |
| ANSWER | `skin_analyses.answers[]` | (`question_id`, `option_value`) | embed: written once with the analysis, read on the result screen | 60 (sum of options of the 7 questions, 50 in the seed, rounded up; 9) |
| PREDICTION | `skin_analyses.predictions[]` | `concern_code` | embed: always read with the analysis | 4 (one per model category; 4) |
| ZONE_ASSESSMENT | `skin_analyses.zone_assessments[]` | `zone_code` | embed: read with the analysis | 6 (one per face zone; 2) |
| QUESTION | `questions` | `_id` = question_id (int); `field_key` unique | collection, reference data | - |
| QUESTION_OPTION | `questions.options[]` | `option_value` | embed: always read with the question, ordered by `position` | 99 (position 1-99; 12) |
| FACE_ZONE | `face_zones` | `_id` = zone_code | collection, reference data | - |
| SKIN_CONCERN | `skin_concerns` | `_id` = concern_code | collection, reference data (text shown on the result screen) | - |
| PHOTO | `photos` | `_id` = photo_id | collection with field `kind` (`ANALYSIS` / `PROGRESS`): one collection for the specialization (polymorphic pattern), `user_id` copied for erasure and URL checks | - |
| ANALYSIS_PHOTO | `photos` with `kind: "ANALYSIS"`: `analysis_id`, `shot_type`, `heatmap_key` | photo `_id` | same document as its PHOTO row (disjoint + total by construction) | 3 per analysis (dictionary rule, enforced by the function / backend; 3) |
| PROGRESS_PHOTO | `photos` with `kind: "PROGRESS"`: `log_id`, `caption` | photo `_id` | same document as its PHOTO row | 1 per log day (UQ log_id) |
| PRODUCT | `products` | `_id` = product_id | collection | - |
| PRODUCT_INGREDIENT | `products.ingredients[]`, ordered by `position` | `ingredient_id` | embed: the INCI list is read with the product on every scan; `inci_name` copied | 200 (position 1-200; 14) |
| INGREDIENT | `ingredients` | `_id` = ingredient_id; `inci_name` unique | collection: shared by many products, changed by curation | - |
| INGREDIENT_FUNCTION | `ingredients.functions[]` (strings) | the value | embed: read with the ingredient | 42 (size of the value set; 4) |
| INGREDIENT_FLAG | `ingredients.flags[]` (strings) | the value | embed: read with the ingredient | 8 (size of the value set; 1) |
| ROUTINE | `routines` | `_id` = routine_id | collection, `user_id` reference; history kept | - |
| ROUTINE_SOURCE | `routines.source_analysis_id` (optional) | - | field: the 1:0..1 relationship becomes an optional reference | 1 |
| ROUTINE_STEP | `routines.steps[]`, ordered by `step_no` | `step_no` | embed: always read with the routine; product name and brand copied | 12 (step_no 1-12; 5) |
| DAILY_LOG | `daily_logs` | `_id` = log_id; unique (`user_id`, `log_date`) | collection: one document per day, grows by one per day, so it cannot be an array in `users` | - (18 per user in the seed) |
| PRODUCT_USE | `daily_logs.product_uses[]` | (`product_id`, `period`) | embed: written and read with the day | 60 (validator `maxItems`, far above two full routines of 12 steps; 7) |

**Check:** 27 of 27 tables mapped once; every array has a stated upper bound, written as `maxItems` in the validators of Task M3. Seed counts (917 rows) after the mapping:

| Collection | Documents | Rows inside (table: count) | Rows |
|---|---|---|---|
| `skin_concerns` | 4 | | 4 |
| `face_zones` | 6 | | 6 |
| `questions` | 7 | options 50 | 57 |
| `ingredients` | 85 | functions 168, flags 14 | 267 |
| `products` | 15 | ingredients 162 | 177 |
| `users` | 7 | reminders 4 | 11 |
| `one_time_tokens` | 3 | | 3 |
| `consents` | 19 | | 19 |
| `refresh_tokens` | 9 | families 7 (distinct `family_id`) | 16 |
| `skin_analyses` | 8 | predictions 32, answers 51, zone assessments 2 | 93 |
| `photos` | 14 | analysis-photo fields 11, progress-photo fields 3 | 28 |
| `routines` | 6 | steps 18, sources 4 | 28 |
| `daily_logs` | 44 | product uses 164 | 208 |
| **Total** | **227** | **690** | **917** |

### Copied values

Each copy relaxes a normalization decision on purpose, for a read that happens far more often than the change.

| Copied value | Why | How it stays correct | What it relaxes |
|---|---|---|---|
| `user_id` in `photos` | erasure and pre-signed URL checks without joining analyses and logs | immutable: a photo never changes owner | FD photo_id -> user_id holds only through analysis_id or log_id (transitive) |
| `user_id` and `family_created_at` in each `refresh_tokens` document | TOKEN_FAMILY has no collection; erasure by `user_id` | written once from the family's first token, never changed | FD family_id -> user_id, created_at (the FN3 split of TOKEN_FAMILY is undone) |
| `inci_name` in `products.ingredients[]` | the scan screen lists names without a `$lookup` | INCI names are fixed by CosIng; a rename runs one `updateMany` with `arrayFilters` | FD ingredient_id -> inci_name repeated per product (transitive) |
| `name`, `brand` in `routines.steps[]` | the routine screen shows them without a `$lookup` | refreshed by the import job when a product changes; a deleted product sets `product_id`, `name`, `brand` to null (the `SET NULL` rule) | FD product_id -> name, brand (transitive) |
| `safety_score`, `flag_summary` in `products` (computed pattern) | derived values read on every scan | recomputed for the affected products when an ingredient's score or flags change (job / function) | derived attributes removed in normalization are stored again |
| `photo_ids[]` in `skin_analyses`, `progress_photo_id` in `daily_logs` | the result screen and the calendar find the photo keys in one read | written in the same transaction as the photo document, removed when the photo is deleted | duplicate of the reverse reference in `photos` |
| not copied: question text and option labels in `answers`, concern names in `predictions` | reference data, joined only on the detail screen and in the export | - | answers keep only the keys, as in BCNF |

### Cross-cutting choices

- **Keys:** `_id` holds the same UUID values as the Oracle keys, as BSON binary subtype 4 (`UUID("...")` in mongosh, `uuidRepresentation="standard"` in PyMongo). Reference data keeps natural keys: `skin_concerns._id` = concern_code, `face_zones._id` = zone_code, `questions._id` = question_id (int) with a unique index on `field_key`.
- **Versioning:** every document has `schema_version: 1`, so later shape changes can be migrated document by document ([schema versioning](https://www.mongodb.com/docs/manual/data-modeling/design-patterns/data-versioning/)).
- **Time:** every moment is a BSON `date` in UTC; calendar days (`date_of_birth`, `log_date`) are dates at 00:00 UTC; `time_of_day` stays `HH:MM` text.
- **Size:** the largest document is a product with 200 ingredients (about 200 x 120 bytes = 24 KB) or an analysis with 60 answers (under 5 KB), far below the 16 MB document limit ([anti-patterns](https://www.mongodb.com/docs/manual/data-modeling/design-antipatterns/)).

## Account and security

### APP_USER

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| user_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | PK | `gen_random_uuid()` | system | personal |
| email | VARCHAR(254) | VARCHAR2(254 CHAR) | string | no | lower-cased, 3-254 chars, one `@`; UQ | | user | personal |
| password_hash | VARCHAR(255) | VARCHAR2(255 CHAR) | string | no | Argon2id hash in PHC format (`$argon2id$...`) | | system | personal |
| first_name | VARCHAR(80) | VARCHAR2(80 CHAR) | string | no | 1-80 chars, trimmed | | user | personal |
| last_name | VARCHAR(80) | VARCHAR2(80 CHAR) | string | no | 1-80 chars, trimmed | | user | personal |
| date_of_birth | DATE | DATE (time 00:00:00) | date | no | age >= 18 at sign-up (the model was trained on adults 18+); not in the future | | user | personal |
| skin_type | VARCHAR(20) | VARCHAR2(20 CHAR) | string | no | value set *skin type* | | user | special |
| main_concern | VARCHAR(40) | VARCHAR2(40 CHAR) | string | no | value set *main concern* | | user | special |
| climate | VARCHAR(30) | VARCHAR2(30 CHAR) | string | no | value set *climate* | | user | personal |
| language | CHAR(2) | CHAR(2 CHAR) | string | no | `ro`, `en` | `ro` | user | personal |
| time_zone | VARCHAR(64) | VARCHAR2(64 CHAR) | string | no | IANA time-zone name (for example `Europe/Bucharest`) | `Europe/Bucharest` | user | personal |
| created_at | TIMESTAMPTZ | TIMESTAMP WITH TIME ZONE, domain `d_utc_ts` | date | no | | `now()` | system | personal |
| email_verified_at | TIMESTAMPTZ | TIMESTAMP WITH TIME ZONE, domain `d_utc_ts` | date | yes | >= created_at; NULL until the address is verified | NULL | system | personal |
| failed_logins | SMALLINT | NUMBER(3) | int | no | 0-100; reset to 0 after a successful login | 0 | system | personal |
| locked_until | TIMESTAMPTZ | TIMESTAMP WITH TIME ZONE, domain `d_utc_ts` | date | yes | set to now + 15 min after 5 failed logins in a row | NULL | system | personal |
| deletion_requested_at | TIMESTAMPTZ | TIMESTAMP WITH TIME ZONE, domain `d_utc_ts` | date | yes | marker of a running account deletion (Task D3.4) | NULL | system | personal |

### ONE_TIME_TOKEN

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| token_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | PK | `gen_random_uuid()` | system | personal |
| user_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> APP_USER, `ON DELETE CASCADE` | | system | personal |
| purpose | VARCHAR(20) | VARCHAR2(20 CHAR) | string | no | `email_verification`, `password_reset` | | system | personal |
| token_hash | CHAR(64) | CHAR(64 CHAR), domain `d_sha256` | string | no | SHA-256 of the token sent by e-mail, lower-case hex `^[0-9a-f]{64}$`; UQ | | system | personal |
| created_at | TIMESTAMPTZ | TIMESTAMP WITH TIME ZONE, domain `d_utc_ts` | date | no | | `now()` | system | personal |
| expires_at | TIMESTAMPTZ | TIMESTAMP WITH TIME ZONE, domain `d_utc_ts` | date | no | > created_at; created_at + 24 h (verification) or + 1 h (reset) | | system | personal |
| used_at | TIMESTAMPTZ | TIMESTAMP WITH TIME ZONE, domain `d_utc_ts` | date | yes | created_at <= used_at <= expires_at; a used token is never accepted again | NULL | system | personal |

### CONSENT

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| consent_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | PK | `gen_random_uuid()` | system | personal |
| user_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> APP_USER, `ON DELETE CASCADE` | | system | personal |
| consent_type | VARCHAR(40) | VARCHAR2(40 CHAR) | string | no | value set *consent type* | | user | personal |
| policy_version | VARCHAR(20) | VARCHAR2(20 CHAR) | string | no | version inside its consent type, `^[0-9]+\.[0-9]+$` (for example `1.0`) | | system | personal |
| granted_at | TIMESTAMPTZ | TIMESTAMP WITH TIME ZONE, domain `d_utc_ts` | date | no | | `now()` | system | personal |
| withdrawn_at | TIMESTAMPTZ | TIMESTAMP WITH TIME ZONE, domain `d_utc_ts` | date | yes | >= granted_at; NULL while the consent is active | NULL | user | personal |

Rows are never updated except to set `withdrawn_at` once: granting the same consent again adds a new row, so the table is the proof of consent (Art. 7(1) GDPR).

### TOKEN_FAMILY

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| family_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | PK; one family per login (session) | `gen_random_uuid()` | system | personal |
| user_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> APP_USER, `ON DELETE CASCADE` | | system | personal |
| created_at | TIMESTAMPTZ | TIMESTAMP WITH TIME ZONE, domain `d_utc_ts` | date | no | | `now()` | system | personal |

### REFRESH_TOKEN

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| token_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | PK | `gen_random_uuid()` | system | personal |
| family_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> TOKEN_FAMILY, `ON DELETE CASCADE` | | system | personal |
| token_hash | CHAR(64) | CHAR(64 CHAR), domain `d_sha256` | string | no | SHA-256, lower-case hex `^[0-9a-f]{64}$`; UQ | | system | personal |
| expires_at | TIMESTAMPTZ | TIMESTAMP WITH TIME ZONE, domain `d_utc_ts` | date | no | issue time + 30 days | | system | personal |
| revoked | BOOLEAN | BOOLEAN | bool | no | true after rotation; presenting a revoked token revokes the whole family | false | system | personal |

At most one non-revoked token per family (rotation revokes the old token and inserts the new one in one transaction).

### REMINDER

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| reminder_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | PK | `gen_random_uuid()` | system | personal |
| user_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> APP_USER, `ON DELETE CASCADE`; UQ (user_id, period) | | system | personal |
| period | VARCHAR(2) | VARCHAR2(2 CHAR), domain `d_period` | string | no | value set *period* | | user | personal |
| time_of_day | TIME | VARCHAR2(5 CHAR) `HH:MM` | string `HH:MM` | no | 00:00-23:59, minute precision, local time of `APP_USER.time_zone`; AM reminders 04:00-11:59, PM 12:00-23:59 | | user | personal |
| enabled | BOOLEAN | BOOLEAN | bool | no | | true | user | personal |

## Skin analysis

### SKIN_ANALYSIS

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| analysis_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | PK | `gen_random_uuid()` | system | special |
| user_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> APP_USER, `ON DELETE CASCADE` | | system | special |
| created_at | TIMESTAMPTZ | TIMESTAMP WITH TIME ZONE, domain `d_utc_ts` | date | no | | `now()` | system | special |
| model_version | VARCHAR(40) | VARCHAR2(40 CHAR) | string | no | `skin_concern_dinov2@` + the first 16 hex digits of the model file hash (`model_sha256` of the ML service) | | ML | none |
| status | VARCHAR(16) | VARCHAR2(16 CHAR) | string | no | value set *analysis status* | | ML | special |
| ood_score | DECIMAL(5,4) | NUMBER(5,4) | double | yes | k-NN cosine distance of the photo to the training photos, 0-2; NULL only for a model without the out-of-scope filter | | ML | special |

### QUESTION

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| question_id | SMALLINT | NUMBER(3) | int | no | PK, 1-999; also the display order | | curated | none |
| field_key | VARCHAR(40) | VARCHAR2(40 CHAR) | string | no | `^[a-z][a-z0-9_]{1,39}$`; the key used by the questionnaire encoder (`ml/features/field_mapping.md`); UQ | | curated | none |
| text | VARCHAR(255) | VARCHAR2(255 CHAR) | string | no | question shown in the app (English, SCIN wording; the app translates it) | | curated | none |
| answer_type | VARCHAR(20) | VARCHAR2(20 CHAR) | string | no | value set *answer type* | | curated | none |

### QUESTION_OPTION

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| question_id | SMALLINT | NUMBER(3) | int | no | FK -> QUESTION, `ON DELETE CASCADE`; PK part | | curated | none |
| option_value | VARCHAR(60) | VARCHAR2(60 CHAR) | string | no | `^[A-Za-z0-9_]{1,60}$` (SCIN codes kept as in the dataset); PK part | | curated | none |
| label | VARCHAR(120) | VARCHAR2(120 CHAR) | string | no | text shown for the option | | curated | none |
| position | SMALLINT | NUMBER(2) | int | no | 1-99; UQ (question_id, position); for `ordinal` questions it is the rank, except the explicit "unknown" option, which comes last | | curated | none |
| is_red_flag | BOOLEAN | BOOLEAN | bool | no | true = the app shows the "see a doctor" message whatever the model says | false | curated | none |

### ANSWER

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| analysis_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> SKIN_ANALYSIS, `ON DELETE CASCADE` | | system | special |
| question_id | SMALLINT | NUMBER(3) | int | no | FK (question_id, option_value) -> QUESTION_OPTION, `ON DELETE RESTRICT` | | user | special |
| option_value | VARCHAR(60) | VARCHAR2(60 CHAR) | string | no | an option of that question | | user | special |

PK (analysis_id, question_id, option_value). One row per ticked option; a skipped question has no row. For `single` and `ordinal` questions the API accepts at most one option.

### FACE_ZONE

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| zone_code | VARCHAR(20) | VARCHAR2(20 CHAR) | string | no | value set *face zone*; PK | | curated | none |
| zone_name | VARCHAR(40) | VARCHAR2(40 CHAR) | string | no | display name; UQ | | curated | none |

### ZONE_ASSESSMENT

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| analysis_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> SKIN_ANALYSIS, `ON DELETE CASCADE`; PK part | | system | special |
| zone_code | VARCHAR(20) | VARCHAR2(20 CHAR) | string | no | FK -> FACE_ZONE, `ON DELETE RESTRICT`; PK part | | ML | special |
| finding | VARCHAR(80) | VARCHAR2(80 CHAR) | string | no | short description of what was seen (for example "enlarged pores") | | ML | special |
| severity | VARCHAR(20) | VARCHAR2(20 CHAR) | string | no | value set *severity* | | ML | special |

Stretch goal (multi-region face chart): the table may stay empty in the MVP.

### SKIN_CONCERN

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| concern_code | VARCHAR(30) | VARCHAR2(30 CHAR) | string | no | value set *model category*; PK | | curated | none |
| name | VARCHAR(60) | VARCHAR2(60 CHAR) | string | no | display name; UQ | | curated | none |
| description | TEXT | VARCHAR2(1000 CHAR) | string | no | plain-language text, informational, never a diagnosis; at most 1,000 chars | | curated | none |

### PREDICTION

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| analysis_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> SKIN_ANALYSIS, `ON DELETE CASCADE`; PK part | | system | special |
| concern_code | VARCHAR(30) | VARCHAR2(30 CHAR) | string | no | FK -> SKIN_CONCERN, `ON DELETE RESTRICT`; PK part | | ML | special |
| probability | DECIMAL(5,4) | NUMBER(5,4), domain `d_probability` | double | no | 0-1 (calibrated) | | ML | special |

Every analysis has one row per model category (4 rows), and the probabilities add up to 1 within 0.001 (checked by the backend and by the tests, not by a constraint).

## Photos (specialization of PHOTO)

### PHOTO

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| photo_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | PK | `gen_random_uuid()` | system | special |
| object_key | VARCHAR(255) | VARCHAR2(255 CHAR) | string | no | random key in the EU object store, `^photos/[0-9a-f-]{36}$`; UQ; no file name, user or type inside it | | system | special |
| content_type | VARCHAR(40) | VARCHAR2(40 CHAR) | string | no | value set *photo content type* | | system | special |
| captured_at | TIMESTAMPTZ | TIMESTAMP WITH TIME ZONE, domain `d_utc_ts` | date | no | not in the future | `now()` | system | special |
| photo_kind | VARCHAR(8) | VARCHAR2(8 CHAR) | string | no | `ANALYSIS`, `PROGRESS` | | system | special |

Disjoint and total: a trigger checks that the subclass row matches `photo_kind`; in Oracle, two deferred SQL assertions reject at commit any PHOTO row without its subclass row, and the app inserts photos only through the package `photo_api`, which writes both rows together (see *Oracle mapping*). PHOTO has no foreign key to the user, so deleting an analysis or an account goes through `photo_api.delete_analysis` or `erase_user`, which delete the photos first. In MongoDB both kinds live in one collection with `kind` and a `oneOf` validator.

### ANALYSIS_PHOTO

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| photo_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | PK, FK -> PHOTO, `ON DELETE CASCADE` | | system | special |
| analysis_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> SKIN_ANALYSIS, `ON DELETE CASCADE`; at most 3 photos per analysis | | system | special |
| shot_type | VARCHAR(20) | VARCHAR2(20 CHAR) | string | no | value set *shot type* | | user | special |
| heatmap_key | VARCHAR(255) | VARCHAR2(255 CHAR) | string | yes | Grad-CAM image key `^heatmaps/[0-9a-f-]{36}$`; unique when present | NULL | ML | special |

### PROGRESS_PHOTO

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| photo_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | PK, FK -> PHOTO, `ON DELETE CASCADE` | | system | special |
| log_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> DAILY_LOG, `ON DELETE CASCADE`; UQ (one photo per log day) | | system | special |
| caption | VARCHAR(140) | VARCHAR2(140 CHAR) | string | yes | | NULL | user | special |

## Products, routines and the daily log

### PRODUCT

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| product_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | PK | `gen_random_uuid()` | system | none |
| barcode | VARCHAR(14) | VARCHAR2(14 CHAR) | string | yes | GTIN digits `^[0-9]{8,14}$` (EAN-8, UPC-A, EAN-13, GTIN-14); unique when present | NULL | import | none |
| name | VARCHAR(160) | VARCHAR2(160 CHAR) | string | no | | | import | none |
| brand | VARCHAR(80) | VARCHAR2(80 CHAR) | string | no | | | import | none |
| category | VARCHAR(40) | VARCHAR2(40 CHAR) | string | no | value set *product category* | | curated | none |
| pack_size | VARCHAR(20) | VARCHAR2(20 CHAR) | string | yes | quantity as printed (for example `150 ml`) | NULL | import | none |
| source | VARCHAR(40) | VARCHAR2(40 CHAR) | string | no | value set *product source* | | system | none |

### INGREDIENT

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| ingredient_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | PK | `gen_random_uuid()` | system | none |
| inci_name | VARCHAR(160) | VARCHAR2(160 CHAR) | string | no | INCI name in upper case as in CosIng (for example `NIACINAMIDE`); UQ (case-insensitive) | | import | none |
| plain_meaning | VARCHAR(255) | VARCHAR2(255 CHAR) | string | no | own plain-language explanation | | curated | none |
| score | SMALLINT | NUMBER(3), domain `d_score` | int | no | 0-100, higher = fewer reasons for caution; band in *Derived values* | | curated | none |

### PRODUCT_INGREDIENT

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| product_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> PRODUCT, `ON DELETE CASCADE`; PK part | | import | none |
| ingredient_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> INGREDIENT, `ON DELETE RESTRICT`; PK part | | import | none |
| position | SMALLINT | NUMBER(3) | int | no | 1-200, order on the INCI list; UQ (product_id, position) | | import | none |

### INGREDIENT_FUNCTION and INGREDIENT_FLAG

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| INGREDIENT_FUNCTION.ingredient_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> INGREDIENT, `ON DELETE CASCADE`; PK part | | import | none |
| INGREDIENT_FUNCTION.function | VARCHAR(30) | VARCHAR2(30 CHAR) | string | no | value set *ingredient function*; PK part | | import | none |
| INGREDIENT_FLAG.ingredient_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> INGREDIENT, `ON DELETE CASCADE`; PK part | | curated | none |
| INGREDIENT_FLAG.flag | VARCHAR(30) | VARCHAR2(30 CHAR) | string | no | value set *ingredient flag*; PK part | | curated | none |

### ROUTINE

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| routine_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | PK | `gen_random_uuid()` | system | personal |
| user_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> APP_USER, `ON DELETE CASCADE` | | system | personal |
| period | VARCHAR(2) | VARCHAR2(2 CHAR), domain `d_period` | string | no | value set *period* | | user | personal |
| complexity_level | VARCHAR(12) | VARCHAR2(12 CHAR) | string | no | value set *routine complexity* | | user | personal |
| created_at | TIMESTAMPTZ | TIMESTAMP WITH TIME ZONE, domain `d_utc_ts` | date | no | | `now()` | system | personal |

The current routine of a period is the latest one (`created_at`); older routines are kept as history.

### ROUTINE_SOURCE

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| routine_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | PK, FK -> ROUTINE, `ON DELETE CASCADE` | | system | special |
| analysis_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> SKIN_ANALYSIS, `ON DELETE CASCADE`; same user as the routine (checked by the data layer) | | system | special |

### ROUTINE_STEP

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| routine_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> ROUTINE, `ON DELETE CASCADE`; PK part | | system | personal |
| step_no | SMALLINT | NUMBER(2) | int | no | 1-12, consecutive inside a routine; PK part | | system | personal |
| product_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | yes | FK -> PRODUCT, `ON DELETE SET NULL`; NULL = no product chosen yet | NULL | user | personal |
| category | VARCHAR(30) | VARCHAR2(30 CHAR) | string | no | value set *step category* | | system | personal |
| instruction | VARCHAR(255) | VARCHAR2(255 CHAR) | string | no | | | system | personal |
| duration_sec | SMALLINT | NUMBER(3) | int | no | 5-900 | | system | personal |

### DAILY_LOG

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| log_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | PK | `gen_random_uuid()` | system | personal |
| user_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> APP_USER, `ON DELETE CASCADE`; UQ (user_id, log_date) | | system | personal |
| log_date | DATE | DATE (time 00:00:00) | date | no | local day of the user; not after today | | user | personal |
| notes | TEXT | VARCHAR2(2000 CHAR) | string | yes | at most 2,000 chars; free text may describe the skin, so it is handled as special-category data | NULL | user | special |

### PRODUCT_USE

| Column | PostgreSQL | Oracle | BSON | Null | Allowed values / range | Default | Origin | GDPR |
|---|---|---|---|---|---|---|---|---|
| log_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> DAILY_LOG, `ON DELETE CASCADE`; PK part | | system | personal |
| product_id | UUID | CHAR(36 CHAR), domain `d_uuid` | binData(4) | no | FK -> PRODUCT, `ON DELETE RESTRICT`; PK part | | user | personal |
| period | VARCHAR(2) | VARCHAR2(2 CHAR), domain `d_period` | string | no | value set *period*; PK part | | user | personal |
| used_at | TIMESTAMPTZ | TIMESTAMP WITH TIME ZONE, domain `d_utc_ts` | date | no | moment the product was ticked | `now()` | system | personal |

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
| REFRESH_TOKEN, TOKEN_FAMILY | until `expires_at` (30 days) | TTL index in MongoDB; scheduled `DELETE` in Oracle; logout revokes the family |
| ONE_TIME_TOKEN | until `expires_at` (1 h or 24 h) | TTL index / scheduled `DELETE` |
| Backups | 4 daily Atlas snapshots | data of a deleted account disappears from the backups within 4 days |
| Reference data (questions, categories, zones, products, ingredients) | no personal data | curated updates |
