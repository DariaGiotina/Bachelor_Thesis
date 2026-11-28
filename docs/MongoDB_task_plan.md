# MongoDB task plan (written 2026-11-28, 30.11-27.12.2026)

Four-week schedule for implementing in MongoDB what Phase O implemented in Oracle (`db/oracle/`): the same schema v1 (18 entities, 27 tables), the same seed data, the same numbered queries and the same functions. It turns Tasks D2.1-D2.3, D3.1 (local part), D3.2 and D3.3 of `docs/DB_task_plan.md` into dated work. The backend data layer, the product import, the tests against the API and the backups (D3.4-D3.7) stay in that plan and run later with Task 5.1. Status legend: DONE, TODO, OPTIONAL. Hours are estimates.

## Minimum result (must exist by Sunday 13.12)

The plan front-loads these four results. Nothing from week 3 starts before all four run from an empty database.

- [ ] **Structure:** every collection created with its `$jsonSchema` validator, its indexes and the views of the derived attributes (`db/mongo/setup.js`, `db/mongo/schema/*.json`). Tasks M3-M4.
- [ ] **Data:** the shared seed loaded with the same keys as Oracle (`db/mongo/seed.js`). Task M5.
- [ ] **Queries:** at least 10 numbered queries, each with its Romanian statement and the same expected count as the Oracle query of the same number (`db/mongo/queries.js`). Task M6.
- [ ] **Function:** `exportUserJson(userId)`, the MongoDB counterpart of the PL/SQL function `export_user_json` (`db/mongo/functions.js`). Task M7.

## Decisions taken before the work starts

- **Server:** Docker `mongo:8.0`, the version Atlas Free runs, started as a single-member replica set (`--replSet rs0`, then `rs.initiate()`), because multi-document transactions need a replica set. The image already contains `mongosh`, so nothing else is installed: scripts run with `docker exec`. Compass is optional, for screenshots.
- **Keys:** `_id` holds the same UUID values as the Oracle keys, stored as BSON binary subtype 4 (`UUID("...")` in mongosh). Reference data keeps its natural key as `_id` (`concern_code`, `zone_code`, `field_key`). The checker compares keys as text.
- **Where the function lives:** Atlas Free runs no server-side JavaScript, and `$function`, `$accumulator` and `$where` are deprecated since MongoDB 8.0 ([8.0 release notes](https://www.mongodb.com/docs/manual/release-notes/8.0/)). So the function is a JavaScript function in a mongosh script, loaded with `load("functions.js")`. Its work is one aggregation pipeline that runs entirely on the server; the function only passes the parameter and returns the result. The backend later calls the same pipeline from Python (D3.4).
- **How a query is counted:** a MongoDB query matches its Oracle twin when it returns the same number of rows (documents after the last stage) and the same values. Embedded arrays are `$unwind`-ed when the Oracle query returns one row per child row.
- **Script language:** identifiers in English, comments and query statements in Romanian, as in the Oracle scripts.
- **Checking tools** (runner, seed generator, checker) live outside the repository, next to the Oracle tools; only the scripts they produce or check are committed.

## Week 1 (30.11-06.12): design and structure - about 12 h

**Task M1: Local server and runner - TODO (2 h)**
- Container `skincare-mongo` from `mongo:8.0` with a named volume and port 27017; replica set initiated once.
- A runner outside the repository with the same steps as the Oracle one: `up`, `version`, `setup`, `seed`, `functions`, `queries`, `dml`, `check`, `all`.
- **Done when:** `rs.status().ok` is 1, `db.version()` starts with 8.0 and a test transaction commits.

**Task M2: Workload and collection mapping (D2.1 + D2.2) - TODO (4 h)**
- List the operations of the app screens (login, refresh, new analysis, history, barcode lookup, product search, routine of the day, tick a product, calendar, progress photos, export, account deletion) and the entities each one reads together.
- Map each of the 27 tables to one collection or to an array inside one, using the list of D2.2: `users` (with `skin_profile` and `reminders`), `consents`, `one_time_tokens`, `refresh_tokens`, `skin_analyses` (with `answers`, `predictions`, `zone_assessments`), `photos` (both subclasses, field `kind`), `questions` (with options), `skin_concerns`, `face_zones`, `products` (ordered `ingredients`, computed `safety_score`), `ingredients` (with `functions` and `flags`), `routines` (with `steps`; ROUTINE_SOURCE becomes the optional field `source_analysis_id`), `daily_logs` (with `product_uses`).
- For each copied value: what is copied, why, how it stays correct and which BCNF decision it relaxes.
- **Deliverable:** section "MongoDB mapping" in `db/data_dictionary.md`.
- **Done when:** every table appears exactly once in the mapping, and every array has an upper bound.

**Task M3: Validators (D2.3, first half) - TODO (4 h)**
- One file per collection, `db/mongo/schema/<collection>.json`: `bsonType`, `required`, `enum`, `minimum` / `maximum`, `pattern`, `minItems` / `maxItems`, `additionalProperties: false` at the top level, `oneOf` for the two photo kinds, a `description` on each rule.
- Every value set and range of `db/data_dictionary.md` is written once, here.
- Rules a validator cannot express (age at least 18, at most 3 photos per analysis, one active refresh token per family) are listed with the place that enforces them: the function, the transaction of M9 or the backend.
- **Done when:** each `CHECK` of `db/oracle/skincare.sql` has a validator rule or a line in that list.

**Task M4: Setup script (D3.2, first half) - TODO (2 h)**
- `db/mongo/setup.js`, safe to run twice: create each collection with its validator (`collMod` if it exists), `validationLevel: "strict"`, `validationAction: "error"`.
- Indexes of D2.3, each with the query it serves: unique e-mail, unique `token_hash`, TTL on `expires_at`, `skin_analyses {user_id: 1, created_at: -1}`, unique barcode with a partial filter, text index on product name and brand, unique `inci_name`, `routines {user_id: 1, period: 1}`, unique `daily_logs {user_id: 1, log_date: 1}`, `photos {user_id: 1, kind: 1}`, unique `object_key`.
- Views that mirror the Oracle views: `v_analysis_result`, `v_prediction_rank`, `v_user_profile`, `v_product_safety` (`db.createView`).
- **Done when:** two runs in a row on an empty database finish without errors, and three invalid sample documents are rejected with error 121 (`DocumentValidationFailure`).

## Week 2 (07.12-13.12): data, queries, function - about 14 h

**Task M5: Seed (D3.2, second half) - TODO (4 h)**
- Extend the seed generator so it also writes `db/mongo/seed.js` from `db/seed/seed_data.yaml`: nested documents built from the child rows, the same UUIDs, dates in UTC.
- **Done when:** the seed loads into the empty database with no validation error, and a count table shows for every Oracle table that its rows equal the documents or array elements of its collection (917 in total).

**Task M6: First 10 queries (D3.3, first half) - TODO (6 h)**
- `db/mongo/queries.js`, numbered like `db/oracle/queries.sql`, with the Oracle statement and expected count above each query. The 10 below are chosen so each uses a different MongoDB construct:

| No. | Question | MongoDB construct | Expected |
|---|---|---|---|
| Q01 | distinct product brands, alphabetical | `$group` + `$sort` | 14 |
| Q02 | products whose name contains "micell", any case | `$regex` with `i`, `$ifNull` | 6 |
| Q03 | analyses with an unusual-photo score in 0.30-0.40 and status `answered` or `uncertain` | range + `$in` + sort | 4 |
| Q04 | users who have not verified their e-mail | `null` / `$exists` | 1 |
| Q07 | answers of a user's first analysis, with question text and option label | `$unwind` + `$lookup` | 7 |
| Q11 | every user with their number of analyses, zero included | `$lookup` + `$size` | 7 |
| Q12 | ingredients used by no product | `$lookup` + empty array | 1 |
| Q17 | products with at least one fragrance ingredient | `$lookup` + `$elemMatch` | 9 |
| Q25 | per category: count, mean, minimum, maximum of probabilities, mean above 0.20 | `$group` + `$match` (HAVING) | 3 |
| Q33 | longest run of consecutive log days per user | `$setWindowFields` | 5 |

- The reference date stays 01.11.2026, as in Oracle, so the counts do not drift.
- **Done when:** the 10 counts match the table and no result is empty.

**Task M7: The function (counterpart of `export_user_json`) - TODO (4 h)**
- `db/mongo/functions.js`: `exportUserJson(userId)` returns one document with the profile, consents, reminders, analyses (predictions, answers, photo keys), routines with steps and log days with products, without password or token hashes, as the Oracle function does.
- Input checked first: a missing or malformed `userId` throws an error with a clear message, like `RAISE_APPLICATION_ERROR` in Oracle.
- **Done when:** for two seed users (one with all data, one with none), the output has the same keys and values as `export_user_json` in Oracle after both are normalized (key order, dates as ISO text).

**Checkpoint, Sunday 13.12:** the runner builds everything from an empty database (`setup`, `seed`, `functions`, `queries`) with one command, and the four boxes at the top are ticked. If something is missing, week 3 finishes it first.

## Week 3 (14.12-20.12): complete and verify - about 12 h

**Task M8: Remaining queries (D3.3, second half) - TODO (4 h)**
- At least 8 more, so the script covers the other constructs: Q14 (`$unionWith`, UNION), Q16 (MINUS), Q21 (`>= ALL`, maximum then match), Q26 (`$dateToString` + `$group`), Q30 (`$bucket` or `$switch`, the CASE bands), Q31 (relational division with `$setIsSubset`), Q32 (latest analysis per user, `$top`), Q34 (top 5 by safety score, `$sort` + `$limit`). More from Q01-Q37 only if time remains.
- **Deliverable:** comparison table for the thesis: query number, SQL construct, MongoDB construct.

**Task M9: Data changes, transactions and a second function - TODO (4 h)**
- `db/mongo/dml.js`, the counterpart of `db/oracle/dml.sql`, on a temporary user erased at the end: `insertOne`, `insertMany`, updates with `$set`, `$inc`, `$push` (`$each`, `$slice`), `$pull`, `$addToSet`, the positional operator and `arrayFilters`, an upsert for the daily log (the `MERGE` of Oracle), `deleteMany`.
- Statements that must fail, each in `try` / `catch` that prints the expected error: duplicate e-mail (E11000), probability 1.2 (validator), a second log on the same day (E11000), a fourth photo on one analysis, a progress photo without its log day.
- Transactions (`session.withTransaction`): refresh-token rotation; reuse of a revoked token revokes the whole family.
- Second function in `functions.js`: `eraseUser(userId)`, the counterpart of `erase_user`: marks the account, then deletes all of the user's documents in every collection in one transaction.
- **Done when:** every expected failure prints OK and no document of the temporary user is left.

**Task M10: Index use and full check - TODO (4 h)**
- `explain("executionStats")` for 3-4 queries: plan stage `IXSCAN`, keys examined close to documents returned.
- Checker outside the repository: runs the whole chain from an empty database, compares every count with the expected one and, when the Oracle container is up, compares the results of the mirrored queries with Oracle (the parity check of D3.6).
- **Done when:** the full run passes twice in a row.

## Week 4 (21.12-27.12): documentation and buffer - about 8 h

**Task M11: `db/README.md` - TODO (1 h)**
- MongoDB section: files, version, how to start the container, run order (`setup.js`, `seed.js`, `functions.js`, `queries.js`, `dml.js`), the rules a validator cannot express and where they are enforced.

**Task M12: Thesis section 4.3 "Modelul fizic al datelor (MongoDB)" (part of D4.1) - TODO (5 h)**
- Mapping table from tables to collections, embedding versus references, the copied values compared with BCNF, validation and indexes, the function, the query comparison table (shortened), the check results.
- At most 3 pages; every new term (document, collection, embedding, validator, index, aggregation pipeline, replica set, transaction) explained where it first appears; references to the MongoDB manual.

**Task M13: Close the month - TODO (2 h)**
- Mark D2.1-D2.3, D3.1 (local part), D3.2 and D3.3 as DONE in `docs/DB_task_plan.md`, each with a short result; journal entry; commit.
- Remaining hours are buffer for anything that slipped.

## OPTIONAL (only after all of the above)

- Run `setup.js`, `seed.js`, `functions.js` and `queries.js` on an Atlas Free cluster in an EU region (the Atlas part of D3.1). The function works there too, because it runs in mongosh, not on the server.
- Fourth page "Document model" in the diagram file (deliverable of D2.2), for a figure in section 4.3.

## Order and total

- M1 -> M2 -> M3 -> M4 -> M5 -> M6 and M7 -> checkpoint -> M8, M9, M10 -> M11, M12, M13.
- Total about 46 h: week 1 12 h, week 2 14 h, week 3 12 h, week 4 8 h.
