# Database task plan (written 2026-11-01)

Plan for the app database, from the finished conceptual design to the MongoDB data layer used by the backend. The relational schema (26 tables in BCNF, `docs/diagrams/skincare_eer.drawio`, `docs/Normalizare_bazei_de_date_Giotina.docx`) is also implemented in PostgreSQL as a reference implementation: it checks the constraints and the queries of the design with the same data, and the MongoDB document model is derived from it. Status legend: DONE, TODO, OPTIONAL. Hours are estimates.

## Assumptions

- **Design inputs (DONE):** EER model in Chen notation with the disjoint, total specialization of PHOTO (2026-10-15); relational schema in BCNF, 26 tables, and the normalization document (2026-10-26); EER-to-relational mapping sheet T1-T26 with rules R1-R10 (2026-10-29). Generators live outside the repository in `D:\facultate\BD_instrumente` (`build_er_diagram.py`, `build_normalizare.py`); only their outputs are committed.
- **One schema, two implementations:** PostgreSQL for the relational reference, MongoDB for the application. Both load the same seed data, use the same identifiers (UUID keys) and answer the same numbered questions, so their results can be compared automatically (Task D3.6).
- **Versions:** MongoDB 8.0, because Atlas Free clusters (formerly M0) run only 8.0 and cannot be upgraded ([Atlas Free limits](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/)); the current server release is 9.0 (GA 28.09.2026, [release notes](https://www.mongodb.com/docs/manual/release-notes/)), so 8.1+ and 9.0 features (validation action `errorAndLog`, validation level `constraint`) are not used. PostgreSQL 18, the current stable major ([released 25.09.2025](https://www.postgresql.org/about/news/postgresql-18-released-3142/); 19 is still a release candidate, GA planned for 19.11.2026), with a script that also runs on 16-17 (keys default to `gen_random_uuid()`, built in since 13; `uuidv7()` is 18 only).
- **Driver:** PyMongo Async API (`AsyncMongoClient`, generally available since PyMongo 4.13, [migration guide](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/reference/migration/)). Motor is not used: it is deprecated, its bug-fix support ended on 14.05.2026 and final support ends on 14.05.2027 ([Motor](https://github.com/mongodb/motor)). No ODM: Beanie 2 also runs on PyMongo Async, but plain queries + Pydantic v2 models keep every query visible and explainable in the thesis.
- **Atlas Free limits that shape the design:** 0.5 GB storage, 100 operations/s, 500 collections, aggregation pipelines of at most 50 stages, 32 MB in-memory sort, no server-side JavaScript (`$where`, `$function`, map-reduce), at most 3 search indexes, daily backup snapshot with 4 kept ([Atlas Free limits](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/)).
- **Script language:** identifiers in English (identical to the diagrams and the code); comments of the SQL and mongosh scripts in Romanian, because the thesis refers to them; application code and its comments in English.
- **Personal data:** seed users are fictitious (`example.com` addresses, throwaway passwords). Face photos, questionnaire answers and analysis results are special-category data under GDPR; no real photo is ever stored in either database, only object keys.
- Every task ends with the thesis, `docs/journal.md` and one commit (2-3 commits per day at most).

## Phase D0: Settle the design before any code

**Task D0.1: Reconcile the data model with the implemented services - TODO (6 h)**
- **Objective:** the EER model, the relational schema, the normalization document, the SQL DDL and the MongoDB validators must describe exactly the same data. The review of 2026-11-01 found these gaps:
  1. `SKIN_ANALYSIS.is_uncertain` (BOOLEAN) cannot hold the three outcomes of the ML service (`ml/serving.py`, `api/ml_service`): `answered`, `uncertain`, `unusual_photo` (out-of-scope filter, Task 4.2b). Replace it with `status` VARCHAR(16) restricted to these values; optionally add `ood_score` DECIMAL(5,4) (kNN score) so a later threshold change can be audited. The FN3 argument of the normalization document still holds: the decision is stored as shown to the user, not recomputed.
  2. `USER` is a reserved word in PostgreSQL and in standard SQL, so `CREATE TABLE user` fails and every query would need quotes. Rename the table to `APP_USER` (the MongoDB collection stays `users`).
  3. `TIMESTAMP` columns become `TIMESTAMPTZ` stored in UTC (MongoDB dates are UTC), so both databases compare equal.
  4. The plan's account flows (e-mail verification, password reset, lockout after failed logins) have no storage in the model. Decide the MVP scope: either add `ONE_TIME_TOKEN(token_id, user_id, purpose, token_hash UQ, expires_at, used_at)` plus `APP_USER.email_verified_at`, `failed_logins`, `locked_until`, or leave them out of the MVP and state it in Chapter 3.
  5. Range of `INGREDIENT.score` and the rule for the derived product safety score (derived attribute in the EER): it becomes a SQL view and a computed field in MongoDB.
  6. How the specialization stays disjoint and total in SQL: discriminator `photo_kind` with a composite foreign key `(photo_id, photo_kind)` in each subclass, or a trigger.
- **Steps:** update `build_er_diagram.py` (pages 1-3) and `build_normalizare.py`; regenerate the draw.io file, the PNG exports, `Schema_ER_relational_Giotina.pdf` and `Normalizare_bazei_de_date_Giotina.docx` + PDF; update thesis 4.1 (sentence on `is_uncertain`, table count if it changes).
- **Done when:** diagrams, normalization document and thesis agree; every table is in BCNF; the table and column list is frozen as "schema v1".

**Task D0.2: Data dictionary and value sets - TODO (5 h)**
- **Deliverable:** `db/data_dictionary.md`: for every column the PostgreSQL type, the BSON type, nullability, allowed values or range, default, origin (user, ML service, import, system) and GDPR class (special category, personal, none) with retention.
- **Value sets to fix:** skin type, main concern (the four model categories), climate, language (`ro`, `en`), consent type, answer type, severity, routine complexity, period (`AM`, `PM`), photo content type (JPEG / PNG / WebP, as accepted by the ML service), shot type, product category, product source, ingredient functions (CosIng function names), ingredient flags.
- **Done when:** every SQL `CHECK` and every `$jsonSchema` `enum` can be written from this file alone.

**Task D0.3: Shared seed data - TODO (8 h)**
- **Reference data:** the four skin concerns of the model; face zones; questionnaire questions and options from `ml/features/field_mapping.md` plus the red-flag questions required by Task 4.2b; about 40 ingredients (INCI name and functions from CosIng, own plain-language meaning, score, flags); about 20 products from Open Beauty Facts with their ingredient lists matched to INCI names.
- **User data:** 6-8 fictitious users; analyses with all three statuses and skipped questions; AM and PM routines with and without a source analysis; about three weeks of daily logs (for streak queries); progress photos with fake object keys (no image files); consents, one of them withdrawn; token families, one with a reused (revoked) token.
- **Edge cases on purpose:** a product without barcode, an ingredient used by no product, a user without any analysis, so that every query of D1.4 and D3.3 returns a non-empty, checkable answer.
- **Single source:** one seed file read by a generator outside the repository (`D:\facultate\BD_instrumente\build_seed.py`) that writes the `INSERT` section of the SQL script and `db/mongo/seed.js`, so both databases hold identical data.
- **Licences:** `db/data_sources.md`: Open Beauty Facts database under ODbL 1.0 and contents under DbCL ([data page](https://world.openbeautyfacts.org/data)), attribution required, share-alike for a published derived database, product images under their own licence (check before use); CosIng reuse terms to verify before import.

## Phase D1: Relational reference implementation (PostgreSQL)

**Task D1.1: PostgreSQL environment - TODO (2 h)**
- PostgreSQL 18 (installer or Docker `postgres:18`), psql and pgAdmin or DBeaver; database `skincare`, schema `skincare`.
- **Done when:** `psql -v ON_ERROR_STOP=1 -f db/postgres/skincare.sql` runs without errors twice in a row on the same database (the script is idempotent).

**Task D1.2: Schema definition (DDL) - TODO (8 h)**
- **File:** `db/postgres/skincare.sql`, numbered sections with a Romanian comment per section and per statement.
- **Content:** `DROP SCHEMA IF EXISTS ... CASCADE`, `CREATE SCHEMA`, `SET search_path`; `CREATE DOMAIN` for repeated value sets (period, probability 0-1, score, SHA-256 hash); `CREATE TABLE` for every table of schema v1 with named constraints (`pk_`, `fk_`, `uq_`, `ck_`), `NOT NULL`, `DEFAULT` (`gen_random_uuid()`, `now()`), column and table `CHECK`s (for example `withdrawn_at >= granted_at`, `step_no >= 1`, `position >= 1`).
- **Referential actions, one reason each:** `ON DELETE CASCADE` for data owned by a user (erasing `APP_USER` erases everything, GDPR right to erasure), `RESTRICT` for reference data still in use (a product inside a routine or log, an ingredient inside a product), `SET NULL` for `ROUTINE_STEP.product_id`.
- **Schema changes:** at least one foreign key added afterwards with `ALTER TABLE ... ADD CONSTRAINT`; adding, renaming and dropping a column; `ALTER COLUMN ... SET DEFAULT`; `DROP ... RESTRICT` vs `CASCADE` shown on a scratch table.
- **Indexes:** on foreign key columns and on the access paths of D2.1, the same list as the MongoDB index plan, so the two can be compared.
- **Least privilege (recommended):** role `skincare_app` with `SELECT, INSERT, UPDATE, DELETE` on user tables and `SELECT` only on reference tables, mirroring the Atlas database user.
- **Done when:** a check script in `BD_instrumente` compares `information_schema` with the table list of `build_er_diagram.py` and finds no difference in tables, columns, types, primary, foreign and unique keys.

**Task D1.3: Data changes and transactions (DML) - TODO (5 h)**
- `INSERT` (one row, several rows, `INSERT ... SELECT`), `UPDATE` (simple, with a subquery, with `CASE`), `DELETE` (simple, with a subquery, erasure of a user that cascades).
- Statements that must fail (duplicate e-mail, probability 1.2, second log on the same day, deleting an ingredient in use), each inside a `DO` block or savepoint that prints the expected error, so the script continues.
- Transactions with `BEGIN ... COMMIT` and `ROLLBACK`: refresh-token rotation (revoke the old token and insert the new one atomically); reuse of a revoked token revokes the whole family.

**Task D1.4: Queries and views - TODO (10 h)**
- **Format:** each query has a Romanian statement ("Să se afișeze ..."), the SQL and the expected row count.
- **Coverage:** selection and projection, `DISTINCT`, aliases, `LIKE` / `ILIKE`, `BETWEEN`, `IN` with a list, `IS NULL`, arithmetic and date expressions, `ORDER BY ASC/DESC`; join in `WHERE`, `INNER JOIN`, self-join, `NATURAL JOIN` / `USING`, `LEFT` / `RIGHT` / `FULL OUTER JOIN`; `UNION`, `INTERSECT`, `EXCEPT`; subqueries with `IN`, row `IN`, scalar `=`, `ANY` / `SOME`, `ALL`, correlated subqueries, `EXISTS` / `NOT EXISTS`; `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`, `COUNT(DISTINCT ...)`, `GROUP BY`, `HAVING`; subqueries in `FROM` and in `SELECT`; `CASE`; relational division; `WITH` (CTE) and window functions.
- **App questions answered (examples):** latest analysis of each user with its top category; analyses per status per month; average probability per concern; products that contain a flagged ingredient; ingredients used by no product; product pairs sharing at least three ingredients (self-join); users without an analysis in the last 30 days; routine adherence in percent; users who ticked every product of their AM routine on a given day (division); longest streak of consecutive log days (window function); users who withdrew a consent; token families with a reused token.
- **Views for the derived attributes removed during normalization:** `v_analysis_result` (overall confidence = largest probability, top concern), `v_prediction_rank` (rank of each prediction), `v_user_profile` (age range from the date of birth), `v_product_safety` (safety score from the ingredient scores); one updatable view `WITH CHECK OPTION` (enabled reminders); a query on a view; `DROP VIEW`.
- **Done when:** every query runs and returns the expected number of rows on the seed data.

**Task D1.5: Procedural extras - OPTIONAL (4 h)**
- PL/pgSQL triggers (specialization totality, at most one active token per family) and a function that exports one user's data as JSON (`json_agg`); program access from Java (JDBC) or Python (psycopg 3).

## Phase D2: Document model (MongoDB design)

**Task D2.1: Workload and access patterns - TODO (4 h)**
- From the Figma screens and the planned endpoints: every read and write operation (login by e-mail, refresh by token hash, create analysis, paginated history, analysis detail, barcode lookup, product text search, ingredient detail, today's routine, tick a product in the daily log, calendar month, progress-photo timeline, consent check before a photo upload, data export, account deletion) with frequency, read/write ratio and the entities read together.
- Follows the MongoDB modelling method: workload first, then relationships, then patterns ([data modeling](https://www.mongodb.com/docs/manual/data-modeling/)).

**Task D2.2: Collections, embedding vs references, patterns - TODO (6 h)**
- **Mapping of the 26 tables to about 11 collections**, one rule per row ([best practices: embed or reference](https://www.mongodb.com/docs/manual/data-modeling/best-practices/)):
  - `users` = APP_USER + `skin_profile` subdocument (the composite attribute of the EER comes back) + `reminders` array (at most two, one per period);
  - `consents` separate (append-only proof of consent, written at different times);
  - `refresh_tokens` = TOKEN_FAMILY + REFRESH_TOKEN, with `family_id` and `user_id` copied into each token;
  - `skin_analyses` = SKIN_ANALYSIS + embedded `answers`, `predictions`, `zone_assessments` and analysis-photo references (read together on the result screen, bounded arrays);
  - `photos` = PHOTO + both subclasses in one collection with a `kind` field (polymorphic pattern, the image of the EER specialization), `user_id` copied for erasure and pre-signed URL checks;
  - `questions` with embedded options; `skin_concerns` and `face_zones` as small reference collections;
  - `products` = PRODUCT + ordered `ingredients` array (extended reference: the INCI name is copied for display) + computed `safety_score` and `flag_summary` (computed pattern), refreshed when an ingredient changes;
  - `ingredients` with embedded `functions` and `flags`;
  - `routines` with embedded `steps` (extended reference to product name and brand) and an optional `source_analysis_id` that replaces ROUTINE_SOURCE;
  - `daily_logs` with embedded `product_uses` and a progress-photo reference.
- **Each denormalization documented:** what is copied, why, how it stays consistent (immutable value or refresh job) and which BCNF decision it relaxes. This links the normalization document to the document model.
- **Cross-cutting choices:** `_id` = UUID (BSON binary subtype 4, `uuidRepresentation="standard"`), the same values as the relational keys; natural keys as `_id` for reference data (`concern_code`, `zone_code`, `field_key`); `schema_version` in every document ([schema versioning](https://www.mongodb.com/docs/manual/data-modeling/design-patterns/data-versioning/)); dates in UTC; size check of the largest document (every array bounded, far below the 16 MB limit; [anti-patterns](https://www.mongodb.com/docs/manual/data-modeling/design-antipatterns/)).
- **Encryption decision:** Queryable Encryption works only on new collections, cannot encrypt fields inside arrays of documents automatically and does not support unique indexes on encrypted fields ([limitations](https://www.mongodb.com/docs/manual/core/queryable-encryption/reference/limitations/)); answers and predictions are arrays of documents, so the MVP relies on Atlas encryption at rest and TLS, and field-level encryption goes to future work.
- **Deliverable:** fourth page "Document model" in `skincare_eer.drawio` (from `build_er_diagram.py`); mapping table for the thesis.

**Task D2.3: Validation rules and index plan - TODO (5 h)**
- **Validators:** one `$jsonSchema` per collection in `db/mongo/schema/<collection>.json`, the single source used by mongosh and by the backend. Draft 4 subset only: `bsonType`, `required`, `enum`, `minimum` / `maximum`, `pattern`, `minItems` / `maxItems`, `additionalProperties: false` at the top level (with `_id` listed), `oneOf` for the two photo kinds; no `$ref`, `default`, `format`, `definitions` or `integer` (use `int` / `long`) ([$jsonSchema](https://www.mongodb.com/docs/manual/reference/operator/query/jsonschema/)); a `description` on each rule, shown in the error since 5.1. `validationLevel: "strict"`, `validationAction: "error"`.
- **Indexes, each with the query it serves (equality, sort, range order):** unique e-mail (stored lower-case); unique `token_hash`, `family_id`, TTL on `expires_at` with `expireAfterSeconds: 0` (single-field only, deleted within about 60 s, [TTL](https://www.mongodb.com/docs/manual/core/index-ttl/)); `skin_analyses {user_id: 1, created_at: -1}`; unique barcode with `partialFilterExpression: {barcode: {$type: "string"}}`, so many products may have no barcode ([partial indexes](https://www.mongodb.com/docs/manual/core/index-partial/)); text index on product name and brand (Atlas Search optional, 3 indexes on Free); unique `inci_name`; `routines {user_id: 1, period: 1}`; unique `daily_logs {user_id: 1, log_date: 1}`; `photos {user_id: 1, kind: 1}` and unique `object_key`; unique `questions.field_key`.

## Phase D3: MongoDB implementation

**Task D3.1: Environments - TODO (3 h)**
- **Atlas:** Free cluster in an EU region (check in the Atlas UI which EU regions offer Free; prefer Frankfurt, Ireland or Belgium); database user `skincare_app` with `readWrite` on database `skincare` only and a separate admin user for setup; IP access list; TLS; connection string in `api/.env` (git-ignored) with `api/.env.example` committed.
- **Local:** Docker `mongo:8.0` started as a single-member replica set (`--replSet rs0` + `rs.initiate()`; transactions need a replica set, checked by a test), mongosh and Compass; same version as Atlas Free, so nothing passes locally that fails on Atlas.

**Task D3.2: Database setup scripts - TODO (5 h)**
- `db/mongo/setup.js` (mongosh, idempotent): create each collection with its validator (`collMod` when it already exists), create the indexes, create the views that mirror the SQL views (`db.createView` with an aggregation pipeline).
- `db/mongo/seed.js` (generated by D0.3): `insertMany` of the shared seed data.
- **Done when:** both scripts run twice, on an empty and on an existing database, without errors; Compass shows validators and indexes; invalid sample documents are rejected with `schemaRulesNotSatisfied` details.

**Task D3.3: CRUD, queries and aggregations - TODO (8 h)**
- `db/mongo/queries.js` with the same numbering as the SQL queries of D1.4.
- `find` with filter, projection, sort, limit and skip; comparison and logical operators, `$in` / `$nin`, `$regex`, `$exists`, `$elemMatch` and array queries; updates with `$set`, `$unset`, `$inc`, `$push` (`$each`, `$slice`), `$pull`, `$addToSet`, positional `$` and `arrayFilters`, upsert; `deleteOne` / `deleteMany`.
- Aggregation: `$match`, `$project`, `$group` (`$sum`, `$avg`, `$min`, `$max`, `$count`), `$sort`, `$limit`, `$unwind`, `$lookup` (also with `let` + `pipeline` for correlated cases), `$facet`, `$bucket`, `$setWindowFields` (rank, streaks), `$unionWith` (UNION), `$setIntersection` / `$setDifference`.
- A multi-document transaction (`session.withTransaction`) for token rotation and account deletion; `explain("executionStats")` for 3-4 queries showing `IXSCAN` and keys examined close to documents returned.
- Respects the Free limits: no server-side JavaScript, at most 50 stages, sorts on indexed fields.
- **Deliverable:** SQL-to-MongoDB comparison table (query number, SQL construct, MongoDB construct) for the thesis.

**Task D3.4: Backend data layer (FastAPI) - TODO (12 h, together with Task 5.1)**
- `api/db/client.py`: one `AsyncMongoClient` per process, opened and closed in the FastAPI lifespan, `uuidRepresentation="standard"`, `tz_aware=True`, timeouts, `retryWrites`.
- `api/db/setup.py`: applies `db/mongo/schema/*.json` and the indexes (startup or CLI); a helper that upgrades documents with an older `schema_version`.
- Repositories per collection with owner-scoped methods: every query on user data filters by the `user_id` taken from the access token, never from the request body (the per-user isolation layer of the security design).
- NoSQL-injection defence: request JSON is never used as a filter; typed Pydantic inputs; keys starting with `$` or containing `.` are rejected.
- Account deletion: resumable job (deletion marker, user documents deleted in a transaction, photo objects deleted from the object store outside the database); data export: one aggregation per collection into a JSON file.
- `/analyze` (Task 5.1) stores the ML decision (`status`, probabilities, model version) in `skin_analyses`.

**Task D3.5: Product and ingredient import - TODO (10 h)**
- **Ingredients:** curated list grown to about 150 INCI names (the most frequent in the imported products): CosIng functions, plain-language meaning, score and flags, stored as a reviewed seed file.
- **Products:** barcode lookup in the Open Beauty Facts API on a cache miss, saved with `source: "openbeautyfacts"`; an initial subset (products with an ingredient list) imported from the JSONL export, sized for the 0.5 GB Free limit; INCI parsing and name normalization (case, synonyms) matched to `ingredients`; unmatched names reported for curation; safety score and flag summary recomputed.
- Attribution to Open Beauty Facts in the app and the thesis (ODbL).

**Task D3.6: Tests - TODO (8 h)**
- pytest against a real `mongod` (Docker `mongo:8.0` replica set), not a mock, because mocks do not reproduce validators, TTL deletion and transactions faithfully.
- **Cases:** each validator rejects a missing required field, a wrong type and a value outside its set; unique indexes (duplicate e-mail, second log on the same day, many products without barcode allowed); TTL index options; owner isolation (user A cannot read, change or delete user B's documents through any repository method); token rotation and reuse detection; after erasure no document of the user is left in any collection; the export contains every collection; the main queries use an index (`explain`).
- **Parity test:** the same seed in PostgreSQL and MongoDB; the numbered queries that exist in both scripts return the same results (skipped when PostgreSQL is not available).

**Task D3.7: Backup, restore and monitoring - TODO (3 h)**
- Atlas Free backups (daily snapshot, 4 kept) plus a scheduled encrypted `mongodump --archive --gzip`; restore test into a scratch database with `mongorestore` (not the `admin` database, not allowed on Free); recovery point and recovery time written down.
- Privacy text: data of a deleted account disappears from the snapshots within the retention period (4 days).
- Monitoring with the metrics available on Free (connections, logical size, network, operation counters); no Performance Advisor on Free, so query plans are checked with `explain`.

## Phase D4: Documentation and delivery

**Task D4.1: Thesis - TODO (8 h)**
- **4.1:** the last paragraph currently says the relational schema is only a check of the model; it becomes the PostgreSQL reference implementation (constraints, views for the derived attributes, the same seed data), with MongoDB as the application database; `status` replaces `is_uncertain`.
- **New 4.3 "Modelul fizic al datelor (MongoDB)":** workload, mapping table from tables to collections, patterns, the deliberate denormalizations compared with BCNF, validation and indexes, the document-model figure.
- **6.x "Stratul de date":** client, repositories, setup, import pipeline. **7.x:** least privilege, TLS, per-user isolation, erasure and export, NoSQL injection, encryption choices. **8.x:** database tests and the SQL-MongoDB parity result.
- **Annex:** compact data dictionary and a pointer to the scripts in `db/`.
- **Budget:** about 6-8 pages in total (whole thesis 60-80 pages); every new term explained where it first appears; real references with links (MongoDB and PostgreSQL manuals, Open Beauty Facts, CosIng).

**Task D4.2: Repository check and hand-over - TODO (2 h)**
- `db/README.md`: run order (PostgreSQL: `psql -f db/postgres/skincare.sql`; MongoDB: `mongosh setup.js`, `seed.js`, `queries.js`), versions, data sources and licences.
- Re-run the consistency checks: diagram vs DDL vs validators.

## Order and dependencies

- D0.1 -> D0.2 -> D0.3 come first; D1 needs D0.3; D2 needs D0.1-D0.2; D3.2 needs D2.3 and D0.3; the parity test (D3.6) needs D1.4 and D3.3; D3.4-D3.5 run together with Task 5.1.
- Recommended sequence: D0.1, D0.2, D0.3, D1.1-D1.4, D2.1-D2.3, D3.1-D3.3, D3.6 (parity part), then D3.4, D3.5, D3.6 (rest), D3.7, D4.
- Total about 120 h (D0 19 h, D1 25 h, D2 15 h, D3 49 h, D4 10 h), plus 4 h optional (D1.5).

## Sources checked on 2026-11-01

- MongoDB: [schema validation](https://www.mongodb.com/docs/manual/core/schema-validation/), [$jsonSchema](https://www.mongodb.com/docs/manual/reference/operator/query/jsonschema/), [TTL indexes](https://www.mongodb.com/docs/manual/core/index-ttl/), [partial indexes](https://www.mongodb.com/docs/manual/core/index-partial/), [design patterns](https://www.mongodb.com/docs/manual/data-modeling/design-patterns/), [anti-patterns](https://www.mongodb.com/docs/manual/data-modeling/design-antipatterns/), [embedding vs references](https://www.mongodb.com/docs/manual/data-modeling/best-practices/), [transactions](https://www.mongodb.com/docs/manual/core/transactions/), [Queryable Encryption limitations](https://www.mongodb.com/docs/manual/core/queryable-encryption/reference/limitations/), [release notes](https://www.mongodb.com/docs/manual/release-notes/), [Atlas Free limits](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/), [MongoDB Search limits](https://www.mongodb.com/docs/search/deployment/feature-compatibility/).
- Python driver: [Migrate to PyMongo Async](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/reference/migration/), [PyMongo release notes](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/reference/release-notes/), [Motor status](https://github.com/mongodb/motor).
- PostgreSQL: [PostgreSQL 18 release](https://www.postgresql.org/about/news/postgresql-18-released-3142/).
- Data: [Open Beauty Facts data and licence](https://world.openbeautyfacts.org/data).
