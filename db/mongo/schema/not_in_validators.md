# Rules a validator cannot express (Task M3)

Every `CHECK` of `db/oracle/skincare.sql` has either a rule in `db/mongo/schema/<collection>.json` or a line below with the place that enforces it. Places: unique index (`setup.js`), the backend, the transactions and functions of Tasks M7 and M9 (`functions.js`, `dml.js`), and the checks of the seed generator and the checker.

## Account, analysis and photo collections: users, consents, one_time_tokens, refresh_tokens, skin_analyses, photos

`$jsonSchema` checks one document at a time and compares a field only with fixed values. Each rule below needs another field, another document, the clock or an aggregate, so it is enforced elsewhere (Task M3).

| Rule | Source | Where it is enforced |
|---|---|---|
| UUID keys have binary subtype 4 (a validator sees only `binData`) | dictionary, Cross-cutting choices | backend (PyMongo `uuidRepresentation="standard"`), seed generator |
| `user_id`, `family_id`, `analysis_id`, `log_id` point to an existing document (MongoDB has no foreign keys) | Oracle `fk_*` constraints | backend repositories; transactions of Task M9 (`dml.js`); the checker of Task M10 compares the keys |
| At least 18 years old at sign-up | `ck_app_user_adult` | backend (sign-up) and the seed generator |
| `date_of_birth` and `log_date` are days at 00:00 UTC, `date_of_birth` not in the future | `ck_app_user_dob_day` | backend, seed generator |
| `email_verified_at >= created_at` | `ck_app_user_verified` | backend (verification flow) |
| E-mail is unique | `uq_app_user_email` | unique index on `users.email` (Task M4) |
| One reminder per period in `users.reminders` | `uq_reminder_user_period` | backend; the AM and PM window of each reminder is a validator rule |
| `expires_at > created_at`; `used_at` between `created_at` and `expires_at` (one-time tokens) | `ck_one_time_token_expiry`, `ck_one_time_token_used` | backend (token issue and use) |
| `withdrawn_at >= granted_at` | `ck_consent_withdrawn` | backend (consent withdrawal), `dml.js` |
| Token hashes are unique; at most one non-revoked refresh token per family | `uq_*_token_hash`, trigger of `plsql.sql` | unique indexes (Task M4); transaction of Task M9 (`dml.js`, token rotation) |
| Refresh token `expires_at` is issue time plus 30 days | dictionary, REFRESH_TOKEN | backend (token issue) |
| `family_created_at` and `user_id` are the same in all tokens of a family | copied values table | backend (written from the first token) |
| Four predictions, one per category, probabilities add up to 1 within 0.001 | dictionary, PREDICTION | backend and seed generator (the validator checks 4 elements and each range) |
| Answers: one option at most for `single` and `ordinal` questions; every `(question_id, option_value)` is an option of that question | `fk_answer_option`, dictionary, ANSWER | backend (reads `questions`), `dml.js` |
| `predictions`, `answers`, `zone_assessments` have no repeated `concern_code`, option or `zone_code` | primary keys of PREDICTION, ANSWER, ZONE_ASSESSMENT | backend, seed generator |
| At most 3 photos per analysis (`photo_ids` is limited to 3, the photos themselves are not counted) | dictionary, ANALYSIS_PHOTO; `photo_api` of `plsql.sql` | function and transaction of Task M9 (`dml.js`) |
| `photo_ids` of an analysis match the photos with that `analysis_id` | copied values table | written in one transaction with the photo (Task M9) |
| `captured_at` and `granted_at` not in the future | dictionary, PHOTO | backend |
| `object_key` and `heatmap_key` are unique when present | `uq_photo_object_key`, unique heatmap | unique indexes (Task M4; `heatmap_key` with a partial filter) |
| One progress photo per log day (`log_id` unique among PROGRESS photos) | `uq_progress_photo_log` | partial unique index on `photos.log_id` (Task M4) |
| A progress photo needs its log day to exist | `fk_progress_photo_log`, dictionary | transaction of Task M9 (`dml.js`) |
| An ANALYSIS photo points to an analysis of the same user | dictionary, ANALYSIS_PHOTO | backend |
| Every PHOTO row has its subclass fields (total) and exactly one kind (disjoint) | assertions and triggers of `plsql.sql` | built in: the `oneOf` of `photos.json` |
| Time-zone name exists in the IANA database | dictionary, APP_USER | backend (the validator checks only the name shape) |

## Reference, routine and log collections

Collections: `questions`, `skin_concerns`, `face_zones`, `products`, `ingredients`, `routines`, `daily_logs`. Each rule comes from `db/oracle/skincare.sql` (constraint name) or from `db/data_dictionary.md`. A `$jsonSchema` validator checks one document on its own: it cannot compare two documents, look at another collection, or know the current date, and it cannot enforce that array elements have distinct keys.

| Rule | Source | Where enforced |
|---|---|---|
| `log_date` has no time of day (a date at 00:00 UTC) | `ck_daily_log_day` | backend (day computed from the user's time zone) and the seed generator check |
| `log_date` is not after today (in the user's time zone) | dictionary, DAILY_LOG.log_date | backend (needs the clock and `users.time_zone`) |
| One log document per user and day | `uq_daily_log_user_date` | unique index `{user_id: 1, log_date: 1}` in `setup.js`; the daily-log tick is an upsert |
| One tick per (product, period) inside `product_uses` | `pk_product_use` | backend and `dml.js`: the update filters on `product_uses` with `$elemMatch` or uses `$addToSet`, so the same pair is never pushed twice |
| `progress_photo_id` points to a PROGRESS photo of the same user and day | `uq_progress_photo_log`, dictionary | transaction in the backend / `dml.js` that writes the photo and the field together |
| `step_no` is consecutive (1, 2, 3, ...) and not repeated inside a routine | `pk_routine_step`, dictionary ROUTINE_STEP.step_no | backend routine builder and the seed generator check (an index cannot enforce uniqueness inside an array) |
| Steps are stored in `step_no` order | mapping "ordered by `step_no`" | backend (builder writes them sorted) |
| `source_analysis_id` belongs to the same user as the routine | dictionary ROUTINE_SOURCE | backend / transaction that creates the routine |
| `name` and `brand` of a step match `products` of its `product_id`; both are null when `product_id` is null | mapping "Copied values" (`fk_routine_step_product`, `ON DELETE SET NULL`) | product import / curation job that refreshes the copies; deleting a product runs one `updateMany` with `arrayFilters` that sets the three fields to null |
| `option_value` is not repeated and `position` is not repeated inside `options` | `pk_question_option`, `uq_question_option_position` | seed generator check and curation script (questions change only by curation) |
| Options are stored in `position` order | mapping "ordered by `position`" | curation script / seed generator |
| `ingredient_id` and `position` are not repeated inside `products.ingredients` | `pk_product_ingredient`, `uq_product_ingredient_position` | product import and the seed generator check |
| Ingredients are stored in `position` order; `inci_name` equals the name in `ingredients` | mapping "Copied values" | product import; a rename runs one `updateMany` with `arrayFilters` |
| `inci_name` is fully upper case (`inci_name = UPPER(inci_name)`) | `ck_ingredient_inci_upper` | validator pattern `^[^a-z]+$` only rejects lower-case ASCII letters (accented lower-case letters pass); the import normalizes with `toUpperCase()` |
| `safety_score` and `flag_summary` equal the values computed from the ingredient scores and flags | dictionary, Derived values | function / job that recomputes them when an ingredient changes; the full check (M10) recomputes and compares |
| A product listed in `daily_logs.product_uses` cannot be deleted | `fk_product_use_product` (no action = restrict) | backend: refuse the delete when `daily_logs` or `routines` still reference the product |
| An ingredient used by a product cannot be deleted | `fk_product_ingredient_ingr` (restrict) | curation job: refuse the delete when `products.ingredients.ingredient_id` still holds it |
| Every `user_id`, `product_id`, `ingredient_id`, `analysis_id` exists (MongoDB has no foreign keys) | all `fk_*` constraints | backend repositories; `dml.js` shows each case; `eraseUser` removes everything owned by a user (the `ON DELETE CASCADE` of the user keys) |
| `name` of a concern, `zone_name` of a zone, `field_key` of a question, `inci_name` of an ingredient are unique; `barcode` is unique when present | `uq_skin_concern_name`, `uq_face_zone_name`, `uq_question_field_key`, `uq_ingredient_inci`, `uq_product_barcode` | unique indexes in `setup.js` (barcode with `partialFilterExpression: {barcode: {$type: "string"}}`, so many products may have none) |
| A routine has at most one current version per period (the latest `created_at` wins) | dictionary ROUTINE | not a constraint: queries take the latest document (index `{user_id: 1, period: 1, created_at: -1}`) |

Rules that the validators do express (so they are not in the table): every value set (`ck_skin_concern_code`, `ck_face_zone_code`, `ck_question_answer_type`, `ck_product_category`, `ck_product_source`, `ck_ingredient_function`, `ck_ingredient_flag`, `ck_routine_complexity`, `ck_routine_step_category`, domain `d_period`), every range (`ck_question_id`, `ck_question_option_position`, `ck_product_ingredient_position`, `ck_routine_step_no`, `ck_routine_step_duration`, domain `d_score`), every pattern (`ck_question_field_key`, `ck_question_option_value`, `ck_product_barcode`), the maximum lengths of the text columns, and the uniqueness of the string elements in `functions`, `flags` and `flag_summary.flags` (`uniqueItems`). Domain `d_utc_ts` needs no rule: a BSON `date` is always UTC.
