# Database

The app stores its data in MongoDB (Atlas, EU region). The same design, schema v1 (18 entities, 27 tables in Boyce-Codd normal form), is also implemented in Oracle as a relational reference implementation. It checks the constraints and the queries of the design on the same seed data, and the MongoDB document model is derived from it.

| Path | Content |
|---|---|
| `data_dictionary.md` | Every table and column: PostgreSQL, Oracle and BSON types, ranges, defaults, origin, GDPR class, value sets, derived values, retention |
| `data_sources.md` | Sources and licences of the reference data (Open Beauty Facts, CosIng) |
| `seed/seed_data.yaml` | Single source of the seed data (fictitious users, `example.com` addresses, no real photos) |
| `oracle/` | Oracle reference implementation (run order below) |
| `postgres/seed.sql` | The same seed rows in PostgreSQL syntax (the first relational target, kept for comparison) |

## Oracle reference implementation

**Version:** Oracle AI Database 26ai Free, Release 23.26.4.0.0 (official container image `container-registry.oracle.com/database/free`), pluggable database `FREEPDB1`. Features used from 23ai on: SQL domains, the `BOOLEAN` type, `IF [NOT] EXISTS` in DDL, multi-row `VALUES`; from 23.26 on: SQL assertions.

**Users:**

| User | Role | Privileges |
|---|---|---|
| `SKINCARE` | owns the schema | create session, table, view, sequence, procedure, trigger, domain, assertion; quota on `USERS` |
| `SKINCARE_APP` | the backend | `CREATE SESSION`; read-only on the reference tables, read-write on the user tables, no `INSERT` on the three photo tables, `EXECUTE` on `photo_api`, `erase_user` and `export_user_json`; a logon trigger sets `CURRENT_SCHEMA = SKINCARE` |

**Run order** (SQL*Plus or SQLcl; client character set UTF-8, for example `NLS_LANG=AMERICAN_AMERICA.AL32UTF8`, otherwise accented letters are stored wrongly):

| Step | Script | Connected as | Content |
|---|---|---|---|
| 1 | `oracle/00_users.sql <pwd_skincare> <pwd_app> <connect>` | SYSTEM | drops and recreates both users, checks that the app user cannot create a table |
| 2 | `oracle/skincare.sql` | SKINCARE | 6 domains, 27 tables with named keys and checks, 18 indexes, schema-change examples, grants, comments (idempotent) |
| 3 | `oracle/plsql.sql` | SKINCARE | 2 assertions (total specialization of PHOTO), 4 triggers, package `photo_api`, functions `erase_user` and `export_user_json` |
| 4 | `oracle/seed.sql` | SKINCARE | 917 seed rows in 27 tables, one transaction |
| 5 | `oracle/dml.sql <pwd_app> <connect>` | SKINCARE, then SKINCARE_APP | inserts, updates, `MERGE`, deletes, 12 statements that must fail, transactions; works on a temporary user that it erases at the end, so the seed data stays unchanged |
| 6 | `oracle/queries.sql` | SKINCARE | 5 views for the derived attributes, 37 numbered queries with their expected row counts, an updatable view `WITH CHECK OPTION`, `DROP VIEW` |

Example with Docker:

```
docker run -d --name skincare-oracle -p 1521:1521 -e ORACLE_PWD=<system password> \
  -v <repo>/db/oracle:/opt/skincare:ro container-registry.oracle.com/database/free:latest
docker exec -e NLS_LANG=AMERICAN_AMERICA.AL32UTF8 skincare-oracle \
  sqlplus -s system/<system password>@//localhost:1521/FREEPDB1 \
  @/opt/skincare/00_users.sql <pwd_skincare> <pwd_app> //localhost:1521/FREEPDB1
docker exec -e NLS_LANG=AMERICAN_AMERICA.AL32UTF8 skincare-oracle \
  sqlplus -s skincare/<pwd_skincare>@//localhost:1521/FREEPDB1 @/opt/skincare/skincare.sql
```

and the same for `plsql.sql`, `seed.sql`, `dml.sql <pwd_app> //localhost:1521/FREEPDB1` and `queries.sql`.

**Integrity rules that need more than a constraint:**

- *Specialization of PHOTO (disjoint, total).* A trigger on each subclass checks `PHOTO.photo_kind`, and a third one forbids changing it. Two deferred SQL assertions reject at commit any photo without its subclass row. The app inserts photos only through `photo_api`, which writes both rows in one call.
- *Deleting an analysis or an account.* `PHOTO` has no foreign key to the user, so a cascade from `APP_USER` would leave photo rows behind, and the assertions refuse that commit. `photo_api.delete_analysis` and `erase_user` delete the photos first. `erase_user` also sets `deletion_requested_at` first, so an interrupted deletion can be resumed.
- *At most one active refresh token per session.* A compound trigger checks each family after the statement (a row trigger cannot count rows of its own table) and locks the family row, so two concurrent rotations cannot both pass.

**Error codes** raised by the PL/SQL code: -20001 analysis not found, -20002 log day not found, -20003 more than 3 photos per analysis, -20004 subclass does not match `photo_kind`, -20005 `photo_kind` changed, -20006 photo not found, -20007 second active refresh token in a family, -20008 user not found.
