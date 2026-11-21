-- =====================================================================================
-- Schema relațională de referință a aplicației (schema v1, 27 de tabele în FNBC)
-- Oracle AI Database 26ai Free, utilizatorul SKINCARE, baza de date conectabilă FREEPDB1
--
-- Sursa tabelelor, a tipurilor și a regulilor: db/data_dictionary.md (coloana Oracle și secțiunea
-- „Oracle mapping”), diagrama docs/diagrams/skincare_eer.drawio și documentul de normalizare.
-- Ordinea de rulare: 00_users.sql (ca SYSTEM), apoi acest script și seed.sql (ca SKINCARE):
--   sql skincare@//localhost:1521/FREEPDB1 @db/oracle/skincare.sql
-- Scriptul este idempotent: șterge tot ce a creat înainte (DROP ... IF EXISTS), deci poate fi
-- rulat de mai multe ori la rând. La prima eroare se oprește (WHENEVER SQLERROR).
--
-- Secțiuni: 1 ștergere | 2 domenii | 3 tabele | 4 indecși | 5 modificări de schemă |
--           6 drepturi pentru SKINCARE_APP | 7 comentarii | 8 verificare
-- =====================================================================================

SET DEFINE OFF
SET SQLBLANKLINES ON
SET SERVEROUTPUT ON
WHENEVER SQLERROR EXIT FAILURE ROLLBACK

-- =====================================================================================
-- 1. Ștergerea obiectelor existente, în ordinea inversă a dependențelor.
--    CASCADE CONSTRAINTS șterge și cheile străine care indică spre tabel, PURGE nu mai trece
--    tabelul prin coșul de reciclare (recycle bin). Domeniile se șterg după tabelele care le folosesc.
-- =====================================================================================
DROP TABLE IF EXISTS tmp_schema_demo_child CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS tmp_schema_demo CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS product_use CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS progress_photo CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS daily_log CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS routine_step CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS routine_source CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS routine CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS ingredient_flag CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS ingredient_function CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS product_ingredient CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS ingredient CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS product CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS analysis_photo CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS photo CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS prediction CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS zone_assessment CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS answer CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS skin_analysis CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS question_option CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS question CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS face_zone CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS skin_concern CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS reminder CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS refresh_token CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS token_family CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS consent CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS one_time_token CASCADE CONSTRAINTS PURGE;
DROP TABLE IF EXISTS app_user CASCADE CONSTRAINTS PURGE;

DROP DOMAIN IF EXISTS d_uuid;
DROP DOMAIN IF EXISTS d_sha256;
DROP DOMAIN IF EXISTS d_utc_ts;
DROP DOMAIN IF EXISTS d_period;
DROP DOMAIN IF EXISTS d_probability;
DROP DOMAIN IF EXISTS d_score;

-- =====================================================================================
-- 2. Domenii SQL (Oracle 23ai+): un tip de date împreună cu regula lui, definite o singură dată
--    și folosite de mai multe coloane. Coloana declarată DOMAIN d_x primește tipul și CHECK-ul
--    domeniului. Numele domeniului ține locul valorii în condiția CHECK.
-- =====================================================================================

-- Identificator UUID păstrat ca text 8-4-4-4-12 cu litere mici, la fel ca în date și în MongoDB
CREATE DOMAIN d_uuid AS CHAR(36 CHAR)
  CONSTRAINT ck_d_uuid
    CHECK (REGEXP_LIKE(d_uuid, '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'));

-- Rezumat SHA-256 în hexazecimal cu litere mici (jetoanele nu se păstrează niciodată în clar)
CREATE DOMAIN d_sha256 AS CHAR(64 CHAR)
  CONSTRAINT ck_d_sha256 CHECK (REGEXP_LIKE(d_sha256, '^[0-9a-f]{64}$'));

-- Moment de timp în UTC: decalajul față de UTC trebuie să fie +00:00
CREATE DOMAIN d_utc_ts AS TIMESTAMP WITH TIME ZONE
  CONSTRAINT ck_d_utc_ts
    CHECK (EXTRACT(TIMEZONE_HOUR FROM d_utc_ts) = 0 AND EXTRACT(TIMEZONE_MINUTE FROM d_utc_ts) = 0);

-- Momentul zilei pentru rutine, mementouri și bifarea produselor
CREATE DOMAIN d_period AS VARCHAR2(2 CHAR)
  CONSTRAINT ck_d_period CHECK (d_period IN ('AM', 'PM'));

-- Probabilitate calibrată întoarsă de serviciul ML, cu 4 zecimale
CREATE DOMAIN d_probability AS NUMBER(5,4)
  CONSTRAINT ck_d_probability CHECK (d_probability BETWEEN 0 AND 1);

-- Scorul unui ingredient: 0-100, mai mare = mai puține motive de precauție
CREATE DOMAIN d_score AS NUMBER(3)
  CONSTRAINT ck_d_score CHECK (d_score BETWEEN 0 AND 100);

-- =====================================================================================
-- 3. Tabele, în ordinea dependențelor (tabelul părinte înaintea tabelului copil).
--    Constrângeri cu nume: pk_ cheie primară, fk_ cheie străină, uq_ unicitate, ck_ verificare.
--    Chei noi: SYS_GUID() (16 octeți aleatori) formatat ca 8-4-4-4-12.
--    Momente noi: FROM_TZ(SYS_EXTRACT_UTC(SYSTIMESTAMP), 'UTC'), adică ora curentă în UTC,
--    indiferent de fusul orar al sesiunii.
--    Acțiuni la ștergere: ON DELETE CASCADE pentru datele unui utilizator (ștergerea contului
--    șterge tot, dreptul la ștergere din GDPR), ON DELETE SET NULL pentru produsul dintr-un pas de
--    rutină, iar fără acțiune (echivalentul RESTRICT) pentru datele de referință încă folosite.
--    Un CHECK cu valoare NULL este considerat îndeplinit, deci coloanele opționale nu au nevoie
--    de „col IS NULL OR ...”.
-- =====================================================================================

-- 3.1 Cont și securitate --------------------------------------------------------------

CREATE TABLE app_user (
  user_id               DOMAIN d_uuid
                        DEFAULT LOWER(REGEXP_REPLACE(RAWTOHEX(SYS_GUID()),
                                '^(.{8})(.{4})(.{4})(.{4})(.{12})$', '\1-\2-\3-\4-\5')) NOT NULL,
  email                 VARCHAR2(254 CHAR) NOT NULL,
  password_hash         VARCHAR2(255 CHAR) NOT NULL,
  first_name            VARCHAR2(80 CHAR) NOT NULL,
  last_name             VARCHAR2(80 CHAR) NOT NULL,
  date_of_birth         DATE NOT NULL,
  skin_type             VARCHAR2(20 CHAR) NOT NULL,
  main_concern          VARCHAR2(40 CHAR) NOT NULL,
  climate               VARCHAR2(30 CHAR) NOT NULL,
  language              CHAR(2 CHAR) DEFAULT 'ro' NOT NULL,
  time_zone             VARCHAR2(64 CHAR) DEFAULT 'Europe/Bucharest' NOT NULL,
  created_at            DOMAIN d_utc_ts DEFAULT FROM_TZ(SYS_EXTRACT_UTC(SYSTIMESTAMP), 'UTC') NOT NULL,
  email_verified_at     DOMAIN d_utc_ts,
  failed_logins         NUMBER(3) DEFAULT 0 NOT NULL,
  locked_until          DOMAIN d_utc_ts,
  deletion_requested_at DOMAIN d_utc_ts,
  CONSTRAINT pk_app_user PRIMARY KEY (user_id),
  CONSTRAINT uq_app_user_email UNIQUE (email),
  CONSTRAINT ck_app_user_email CHECK (email = LOWER(email) AND LENGTH(email) BETWEEN 3 AND 254
                                      AND REGEXP_COUNT(email, '@') = 1),
  CONSTRAINT ck_app_user_password CHECK (password_hash LIKE '$argon2id$%'),
  CONSTRAINT ck_app_user_names CHECK (first_name = TRIM(first_name) AND last_name = TRIM(last_name)),
  -- cel puțin 18 ani la înregistrare (modelul a fost antrenat pe adulți)
  CONSTRAINT ck_app_user_adult CHECK (date_of_birth <= ADD_MONTHS(TRUNC(SYS_EXTRACT_UTC(created_at)), -216)),
  CONSTRAINT ck_app_user_dob_day CHECK (date_of_birth = TRUNC(date_of_birth)),
  CONSTRAINT ck_app_user_skin_type CHECK (skin_type IN ('normal', 'dry', 'oily', 'combination', 'sensitive')),
  CONSTRAINT ck_app_user_main_concern CHECK (main_concern IN ('acne', 'redness', 'dryness', 'oiliness_pores',
                                             'sensitivity', 'hyperpigmentation', 'signs_of_aging', 'none')),
  CONSTRAINT ck_app_user_climate CHECK (climate IN ('temperate', 'humid', 'dry', 'cold')),
  CONSTRAINT ck_app_user_language CHECK (language IN ('ro', 'en')),
  CONSTRAINT ck_app_user_time_zone CHECK (REGEXP_LIKE(time_zone, '^[A-Za-z_]+(/[A-Za-z0-9_+-]+)*$')),
  CONSTRAINT ck_app_user_verified CHECK (email_verified_at >= created_at),
  CONSTRAINT ck_app_user_failed_logins CHECK (failed_logins BETWEEN 0 AND 100)
);

CREATE TABLE one_time_token (
  token_id    DOMAIN d_uuid
              DEFAULT LOWER(REGEXP_REPLACE(RAWTOHEX(SYS_GUID()),
                      '^(.{8})(.{4})(.{4})(.{4})(.{12})$', '\1-\2-\3-\4-\5')) NOT NULL,
  user_id     DOMAIN d_uuid NOT NULL,
  purpose     VARCHAR2(20 CHAR) NOT NULL,
  token_hash  DOMAIN d_sha256 NOT NULL,
  created_at  DOMAIN d_utc_ts DEFAULT FROM_TZ(SYS_EXTRACT_UTC(SYSTIMESTAMP), 'UTC') NOT NULL,
  expires_at  DOMAIN d_utc_ts NOT NULL,
  used_at     DOMAIN d_utc_ts,
  CONSTRAINT pk_one_time_token PRIMARY KEY (token_id),
  CONSTRAINT fk_one_time_token_user FOREIGN KEY (user_id) REFERENCES app_user (user_id) ON DELETE CASCADE,
  CONSTRAINT uq_one_time_token_hash UNIQUE (token_hash),
  CONSTRAINT ck_one_time_token_purpose CHECK (purpose IN ('email_verification', 'password_reset')),
  CONSTRAINT ck_one_time_token_expiry CHECK (expires_at > created_at),
  -- un jeton se folosește o singură dată, înainte să expire
  CONSTRAINT ck_one_time_token_used CHECK (used_at BETWEEN created_at AND expires_at)
);

CREATE TABLE consent (
  consent_id      DOMAIN d_uuid
                  DEFAULT LOWER(REGEXP_REPLACE(RAWTOHEX(SYS_GUID()),
                          '^(.{8})(.{4})(.{4})(.{4})(.{12})$', '\1-\2-\3-\4-\5')) NOT NULL,
  user_id         DOMAIN d_uuid NOT NULL,
  consent_type    VARCHAR2(40 CHAR) NOT NULL,
  policy_version  VARCHAR2(20 CHAR) NOT NULL,
  granted_at      DOMAIN d_utc_ts DEFAULT FROM_TZ(SYS_EXTRACT_UTC(SYSTIMESTAMP), 'UTC') NOT NULL,
  withdrawn_at    DOMAIN d_utc_ts,
  CONSTRAINT pk_consent PRIMARY KEY (consent_id),
  CONSTRAINT fk_consent_user FOREIGN KEY (user_id) REFERENCES app_user (user_id) ON DELETE CASCADE,
  CONSTRAINT ck_consent_type CHECK (consent_type IN ('privacy_policy', 'photo_processing', 'health_data',
                                                     'reminders')),
  CONSTRAINT ck_consent_version CHECK (REGEXP_LIKE(policy_version, '^[0-9]+\.[0-9]+$')),
  CONSTRAINT ck_consent_withdrawn CHECK (withdrawn_at >= granted_at)
);

CREATE TABLE token_family (
  family_id   DOMAIN d_uuid
              DEFAULT LOWER(REGEXP_REPLACE(RAWTOHEX(SYS_GUID()),
                      '^(.{8})(.{4})(.{4})(.{4})(.{12})$', '\1-\2-\3-\4-\5')) NOT NULL,
  user_id     DOMAIN d_uuid NOT NULL,
  created_at  DOMAIN d_utc_ts DEFAULT FROM_TZ(SYS_EXTRACT_UTC(SYSTIMESTAMP), 'UTC') NOT NULL,
  CONSTRAINT pk_token_family PRIMARY KEY (family_id),
  CONSTRAINT fk_token_family_user FOREIGN KEY (user_id) REFERENCES app_user (user_id) ON DELETE CASCADE
);

-- cel mult un jeton activ (revoked = FALSE) pe familie: declanșator compus în ziua a doua (Task O5)
CREATE TABLE refresh_token (
  token_id    DOMAIN d_uuid
              DEFAULT LOWER(REGEXP_REPLACE(RAWTOHEX(SYS_GUID()),
                      '^(.{8})(.{4})(.{4})(.{4})(.{12})$', '\1-\2-\3-\4-\5')) NOT NULL,
  family_id   DOMAIN d_uuid NOT NULL,
  token_hash  DOMAIN d_sha256 NOT NULL,
  expires_at  DOMAIN d_utc_ts NOT NULL,
  revoked     BOOLEAN DEFAULT FALSE NOT NULL,
  CONSTRAINT pk_refresh_token PRIMARY KEY (token_id),
  CONSTRAINT fk_refresh_token_family FOREIGN KEY (family_id) REFERENCES token_family (family_id)
    ON DELETE CASCADE,
  CONSTRAINT uq_refresh_token_hash UNIQUE (token_hash)
);

CREATE TABLE reminder (
  reminder_id  DOMAIN d_uuid
               DEFAULT LOWER(REGEXP_REPLACE(RAWTOHEX(SYS_GUID()),
                       '^(.{8})(.{4})(.{4})(.{4})(.{12})$', '\1-\2-\3-\4-\5')) NOT NULL,
  user_id      DOMAIN d_uuid NOT NULL,
  period       DOMAIN d_period NOT NULL,
  time_of_day  VARCHAR2(5 CHAR) NOT NULL,
  enabled      BOOLEAN DEFAULT TRUE NOT NULL,
  CONSTRAINT pk_reminder PRIMARY KEY (reminder_id),
  CONSTRAINT fk_reminder_user FOREIGN KEY (user_id) REFERENCES app_user (user_id) ON DELETE CASCADE,
  CONSTRAINT uq_reminder_user_period UNIQUE (user_id, period),
  -- ora locală HH:MM (Oracle nu are un tip pentru ora din zi), dimineața 04:00-11:59, seara 12:00-23:59
  CONSTRAINT ck_reminder_time CHECK (REGEXP_LIKE(time_of_day, '^([01][0-9]|2[0-3]):[0-5][0-9]$')),
  CONSTRAINT ck_reminder_window CHECK ((period = 'AM' AND time_of_day BETWEEN '04:00' AND '11:59')
                                       OR (period = 'PM' AND time_of_day BETWEEN '12:00' AND '23:59'))
);

-- 3.2 Analiza pielii --------------------------------------------------------------------

CREATE TABLE skin_concern (
  concern_code  VARCHAR2(30 CHAR) NOT NULL,
  name          VARCHAR2(60 CHAR) NOT NULL,
  description   VARCHAR2(1000 CHAR) NOT NULL,
  CONSTRAINT pk_skin_concern PRIMARY KEY (concern_code),
  CONSTRAINT uq_skin_concern_name UNIQUE (name),
  -- cele patru categorii ale modelului exportat, în ordinea lui
  CONSTRAINT ck_skin_concern_code CHECK (concern_code IN ('acne', 'eczema_dermatitis', 'redness_rosacea',
                                                          'normal_other'))
);

CREATE TABLE face_zone (
  zone_code  VARCHAR2(20 CHAR) NOT NULL,
  zone_name  VARCHAR2(40 CHAR) NOT NULL,
  CONSTRAINT pk_face_zone PRIMARY KEY (zone_code),
  CONSTRAINT uq_face_zone_name UNIQUE (zone_name),
  CONSTRAINT ck_face_zone_code CHECK (zone_code IN ('forehead', 'nose', 'left_cheek', 'right_cheek', 'chin',
                                                    'jawline'))
);

CREATE TABLE question (
  question_id  NUMBER(3) NOT NULL,
  field_key    VARCHAR2(40 CHAR) NOT NULL,
  text         VARCHAR2(255 CHAR) NOT NULL,
  answer_type  VARCHAR2(20 CHAR) NOT NULL,
  CONSTRAINT pk_question PRIMARY KEY (question_id),
  CONSTRAINT uq_question_field_key UNIQUE (field_key),
  CONSTRAINT ck_question_id CHECK (question_id BETWEEN 1 AND 999),
  CONSTRAINT ck_question_field_key CHECK (REGEXP_LIKE(field_key, '^[a-z][a-z0-9_]{1,39}$')),
  CONSTRAINT ck_question_answer_type CHECK (answer_type IN ('single', 'multi', 'ordinal'))
);

CREATE TABLE question_option (
  question_id   NUMBER(3) NOT NULL,
  option_value  VARCHAR2(60 CHAR) NOT NULL,
  label         VARCHAR2(120 CHAR) NOT NULL,
  position      NUMBER(2) NOT NULL,
  is_red_flag   BOOLEAN DEFAULT FALSE NOT NULL,
  CONSTRAINT pk_question_option PRIMARY KEY (question_id, option_value),
  CONSTRAINT fk_question_option_question FOREIGN KEY (question_id) REFERENCES question (question_id)
    ON DELETE CASCADE,
  CONSTRAINT uq_question_option_position UNIQUE (question_id, position),
  CONSTRAINT ck_question_option_value CHECK (REGEXP_LIKE(option_value, '^[A-Za-z0-9_]{1,60}$')),
  CONSTRAINT ck_question_option_position CHECK (position BETWEEN 1 AND 99)
);

CREATE TABLE skin_analysis (
  analysis_id    DOMAIN d_uuid
                 DEFAULT LOWER(REGEXP_REPLACE(RAWTOHEX(SYS_GUID()),
                         '^(.{8})(.{4})(.{4})(.{4})(.{12})$', '\1-\2-\3-\4-\5')) NOT NULL,
  user_id        DOMAIN d_uuid NOT NULL,
  created_at     DOMAIN d_utc_ts DEFAULT FROM_TZ(SYS_EXTRACT_UTC(SYSTIMESTAMP), 'UTC') NOT NULL,
  model_version  VARCHAR2(40 CHAR) NOT NULL,
  status         VARCHAR2(16 CHAR) NOT NULL,
  ood_score      NUMBER(5,4),
  CONSTRAINT pk_skin_analysis PRIMARY KEY (analysis_id),
  CONSTRAINT fk_skin_analysis_user FOREIGN KEY (user_id) REFERENCES app_user (user_id) ON DELETE CASCADE,
  -- numele modelului urmat de primele 16 cifre hexazecimale ale rezumatului fișierului ONNX
  CONSTRAINT ck_skin_analysis_model CHECK (REGEXP_LIKE(model_version, '^skin_concern_dinov2@[0-9a-f]{16}$')),
  -- cele trei rezultate ale serviciului ML: categorie afișată, nesigur, fotografie neobișnuită
  CONSTRAINT ck_skin_analysis_status CHECK (status IN ('answered', 'uncertain', 'unusual_photo')),
  CONSTRAINT ck_skin_analysis_ood CHECK (ood_score BETWEEN 0 AND 2)
);

-- o linie pentru fiecare variantă bifată, o întrebare sărită nu are nicio linie
CREATE TABLE answer (
  analysis_id   DOMAIN d_uuid NOT NULL,
  question_id   NUMBER(3) NOT NULL,
  option_value  VARCHAR2(60 CHAR) NOT NULL,
  CONSTRAINT pk_answer PRIMARY KEY (analysis_id, question_id, option_value),
  CONSTRAINT fk_answer_analysis FOREIGN KEY (analysis_id) REFERENCES skin_analysis (analysis_id)
    ON DELETE CASCADE,
  CONSTRAINT fk_answer_option FOREIGN KEY (question_id, option_value)
    REFERENCES question_option (question_id, option_value)
);

CREATE TABLE zone_assessment (
  analysis_id  DOMAIN d_uuid NOT NULL,
  zone_code    VARCHAR2(20 CHAR) NOT NULL,
  finding      VARCHAR2(80 CHAR) NOT NULL,
  severity     VARCHAR2(20 CHAR) NOT NULL,
  CONSTRAINT pk_zone_assessment PRIMARY KEY (analysis_id, zone_code),
  CONSTRAINT fk_zone_assessment_analysis FOREIGN KEY (analysis_id) REFERENCES skin_analysis (analysis_id)
    ON DELETE CASCADE,
  CONSTRAINT fk_zone_assessment_zone FOREIGN KEY (zone_code) REFERENCES face_zone (zone_code),
  CONSTRAINT ck_zone_assessment_severity CHECK (severity IN ('mild', 'moderate', 'pronounced'))
);

-- patru linii pe analiză, câte una pe categorie; suma de 1 o verifică backend-ul și testele
CREATE TABLE prediction (
  analysis_id   DOMAIN d_uuid NOT NULL,
  concern_code  VARCHAR2(30 CHAR) NOT NULL,
  probability   DOMAIN d_probability NOT NULL,
  CONSTRAINT pk_prediction PRIMARY KEY (analysis_id, concern_code),
  CONSTRAINT fk_prediction_analysis FOREIGN KEY (analysis_id) REFERENCES skin_analysis (analysis_id)
    ON DELETE CASCADE,
  CONSTRAINT fk_prediction_concern FOREIGN KEY (concern_code) REFERENCES skin_concern (concern_code)
);

-- 3.3 Fotografii: specializarea disjunctă și totală PHOTO -> ANALYSIS_PHOTO | PROGRESS_PHOTO --
-- Disjuncția și totalitatea se impun în ziua a doua (Task O5): un declanșator pe fiecare subclasă
-- verifică photo_kind, iar pachetul photo_api scrie PHOTO și subclasa în același apel.

CREATE TABLE photo (
  photo_id      DOMAIN d_uuid
                DEFAULT LOWER(REGEXP_REPLACE(RAWTOHEX(SYS_GUID()),
                        '^(.{8})(.{4})(.{4})(.{4})(.{12})$', '\1-\2-\3-\4-\5')) NOT NULL,
  object_key    VARCHAR2(255 CHAR) NOT NULL,
  content_type  VARCHAR2(40 CHAR) NOT NULL,
  captured_at   DOMAIN d_utc_ts DEFAULT FROM_TZ(SYS_EXTRACT_UTC(SYSTIMESTAMP), 'UTC') NOT NULL,
  photo_kind    VARCHAR2(8 CHAR) NOT NULL,
  CONSTRAINT pk_photo PRIMARY KEY (photo_id),
  CONSTRAINT uq_photo_object_key UNIQUE (object_key),
  -- cheie aleatoare în depozitul de obiecte din UE, fără nume de fișier sau utilizator
  CONSTRAINT ck_photo_object_key CHECK (REGEXP_LIKE(object_key, '^photos/[0-9a-f-]{36}$')),
  CONSTRAINT ck_photo_content_type CHECK (content_type IN ('image/jpeg', 'image/png', 'image/webp')),
  CONSTRAINT ck_photo_kind CHECK (photo_kind IN ('ANALYSIS', 'PROGRESS'))
);

CREATE TABLE analysis_photo (
  photo_id     DOMAIN d_uuid NOT NULL,
  analysis_id  DOMAIN d_uuid NOT NULL,
  shot_type    VARCHAR2(20 CHAR) NOT NULL,
  heatmap_key  VARCHAR2(255 CHAR),
  CONSTRAINT pk_analysis_photo PRIMARY KEY (photo_id),
  CONSTRAINT fk_analysis_photo_photo FOREIGN KEY (photo_id) REFERENCES photo (photo_id) ON DELETE CASCADE,
  CONSTRAINT fk_analysis_photo_analysis FOREIGN KEY (analysis_id) REFERENCES skin_analysis (analysis_id)
    ON DELETE CASCADE,
  -- UNIQUE acceptă mai multe valori NULL: doar hărțile Grad-CAM existente trebuie să fie distincte
  CONSTRAINT uq_analysis_photo_heatmap UNIQUE (heatmap_key),
  CONSTRAINT ck_analysis_photo_shot CHECK (shot_type IN ('front', 'left', 'right')),
  CONSTRAINT ck_analysis_photo_heatmap CHECK (REGEXP_LIKE(heatmap_key, '^heatmaps/[0-9a-f-]{36}$'))
);

-- 3.4 Produse și ingrediente ------------------------------------------------------------

CREATE TABLE product (
  product_id  DOMAIN d_uuid
              DEFAULT LOWER(REGEXP_REPLACE(RAWTOHEX(SYS_GUID()),
                      '^(.{8})(.{4})(.{4})(.{4})(.{12})$', '\1-\2-\3-\4-\5')) NOT NULL,
  barcode     VARCHAR2(14 CHAR),
  name        VARCHAR2(160 CHAR) NOT NULL,
  brand       VARCHAR2(80 CHAR) NOT NULL,
  category    VARCHAR2(40 CHAR) NOT NULL,
  -- „size” este cuvânt rezervat în Oracle, de aceea coloana se numește pack_size
  pack_size   VARCHAR2(20 CHAR),
  source      VARCHAR2(40 CHAR) NOT NULL,
  CONSTRAINT pk_product PRIMARY KEY (product_id),
  CONSTRAINT uq_product_barcode UNIQUE (barcode),
  -- GTIN: EAN-8, UPC-A, EAN-13 sau GTIN-14
  CONSTRAINT ck_product_barcode CHECK (REGEXP_LIKE(barcode, '^[0-9]{8,14}$')),
  CONSTRAINT ck_product_category CHECK (category IN ('cleanser', 'toner', 'serum', 'moisturizer', 'sunscreen',
                                                     'exfoliant', 'mask', 'eye_care', 'other')),
  CONSTRAINT ck_product_source CHECK (source IN ('curated', 'openbeautyfacts'))
);

CREATE TABLE ingredient (
  ingredient_id  DOMAIN d_uuid
                 DEFAULT LOWER(REGEXP_REPLACE(RAWTOHEX(SYS_GUID()),
                         '^(.{8})(.{4})(.{4})(.{4})(.{12})$', '\1-\2-\3-\4-\5')) NOT NULL,
  inci_name      VARCHAR2(160 CHAR) NOT NULL,
  plain_meaning  VARCHAR2(255 CHAR) NOT NULL,
  score          DOMAIN d_score NOT NULL,
  CONSTRAINT pk_ingredient PRIMARY KEY (ingredient_id),
  -- numele INCI se scrie cu majuscule, deci unicitatea simplă este și fără diferența de majuscule
  CONSTRAINT uq_ingredient_inci UNIQUE (inci_name),
  CONSTRAINT ck_ingredient_inci_upper CHECK (inci_name = UPPER(inci_name))
);

CREATE TABLE product_ingredient (
  product_id     DOMAIN d_uuid NOT NULL,
  ingredient_id  DOMAIN d_uuid NOT NULL,
  position       NUMBER(3) NOT NULL,
  CONSTRAINT pk_product_ingredient PRIMARY KEY (product_id, ingredient_id),
  CONSTRAINT fk_product_ingredient_product FOREIGN KEY (product_id) REFERENCES product (product_id)
    ON DELETE CASCADE,
  -- un ingredient folosit de un produs nu poate fi șters (fără acțiune = RESTRICT)
  CONSTRAINT fk_product_ingredient_ingr FOREIGN KEY (ingredient_id) REFERENCES ingredient (ingredient_id),
  CONSTRAINT uq_product_ingredient_position UNIQUE (product_id, position),
  CONSTRAINT ck_product_ingredient_position CHECK (position BETWEEN 1 AND 200)
);

-- „function” este acceptat în SQL, dar este cuvânt rezervat în PL/SQL: acolo se scrie "FUNCTION"
CREATE TABLE ingredient_function (
  ingredient_id  DOMAIN d_uuid NOT NULL,
  function       VARCHAR2(30 CHAR) NOT NULL,
  CONSTRAINT pk_ingredient_function PRIMARY KEY (ingredient_id, function),
  CONSTRAINT fk_ingredient_function_ingr FOREIGN KEY (ingredient_id) REFERENCES ingredient (ingredient_id)
    ON DELETE CASCADE,
  -- denumirile de funcții din CosIng, cu litere mici și _
  CONSTRAINT ck_ingredient_function CHECK (function IN (
    'abrasive', 'absorbent', 'antimicrobial', 'antioxidant', 'antiperspirant', 'antistatic', 'astringent',
    'binding', 'bleaching', 'buffering', 'chelating', 'cleansing', 'colorant', 'denaturant', 'deodorant',
    'emollient', 'emulsifying', 'emulsion_stabilising', 'exfoliating', 'film_forming', 'foam_boosting',
    'gel_forming', 'hair_conditioning', 'humectant', 'keratolytic', 'masking', 'moisturising', 'opacifying',
    'perfuming', 'plasticiser', 'preservative', 'refreshing', 'skin_conditioning', 'skin_protecting',
    'smoothing', 'solvent', 'soothing', 'surfactant', 'tonic', 'uv_absorber', 'uv_filter',
    'viscosity_controlling'))
);

CREATE TABLE ingredient_flag (
  ingredient_id  DOMAIN d_uuid NOT NULL,
  flag           VARCHAR2(30 CHAR) NOT NULL,
  CONSTRAINT pk_ingredient_flag PRIMARY KEY (ingredient_id, flag),
  CONSTRAINT fk_ingredient_flag_ingr FOREIGN KEY (ingredient_id) REFERENCES ingredient (ingredient_id)
    ON DELETE CASCADE,
  CONSTRAINT ck_ingredient_flag CHECK (flag IN ('fragrance', 'fragrance_allergen', 'essential_oil',
                                                'drying_alcohol', 'exfoliating_acid', 'retinoid', 'comedogenic',
                                                'formaldehyde_releaser'))
);

-- 3.5 Rutine și jurnalul zilnic ---------------------------------------------------------

CREATE TABLE routine (
  routine_id        DOMAIN d_uuid
                    DEFAULT LOWER(REGEXP_REPLACE(RAWTOHEX(SYS_GUID()),
                            '^(.{8})(.{4})(.{4})(.{4})(.{12})$', '\1-\2-\3-\4-\5')) NOT NULL,
  user_id           DOMAIN d_uuid NOT NULL,
  period            DOMAIN d_period NOT NULL,
  complexity_level  VARCHAR2(12 CHAR) NOT NULL,
  created_at        DOMAIN d_utc_ts DEFAULT FROM_TZ(SYS_EXTRACT_UTC(SYSTIMESTAMP), 'UTC') NOT NULL,
  CONSTRAINT pk_routine PRIMARY KEY (routine_id),
  CONSTRAINT fk_routine_user FOREIGN KEY (user_id) REFERENCES app_user (user_id) ON DELETE CASCADE,
  CONSTRAINT ck_routine_complexity CHECK (complexity_level IN ('basic', 'intermediate', 'advanced'))
);

-- legătura opțională 1:N „rutina se bazează pe analiza”, în tabel propriu (fără NULL în ROUTINE)
CREATE TABLE routine_source (
  routine_id   DOMAIN d_uuid NOT NULL,
  analysis_id  DOMAIN d_uuid NOT NULL,
  CONSTRAINT pk_routine_source PRIMARY KEY (routine_id),
  CONSTRAINT fk_routine_source_routine FOREIGN KEY (routine_id) REFERENCES routine (routine_id)
    ON DELETE CASCADE,
  CONSTRAINT fk_routine_source_analysis FOREIGN KEY (analysis_id) REFERENCES skin_analysis (analysis_id)
    ON DELETE CASCADE
);

-- entitate slabă: cheia este (rutina, numărul pasului). Cheia străină spre PRODUCT se adaugă
-- ulterior, în secțiunea 5, ca exemplu de ALTER TABLE ... ADD CONSTRAINT
CREATE TABLE routine_step (
  routine_id    DOMAIN d_uuid NOT NULL,
  step_no       NUMBER(2) NOT NULL,
  product_id    DOMAIN d_uuid,
  category      VARCHAR2(30 CHAR) NOT NULL,
  instruction   VARCHAR2(255 CHAR) NOT NULL,
  duration_sec  NUMBER(3) NOT NULL,
  CONSTRAINT pk_routine_step PRIMARY KEY (routine_id, step_no),
  CONSTRAINT fk_routine_step_routine FOREIGN KEY (routine_id) REFERENCES routine (routine_id)
    ON DELETE CASCADE,
  CONSTRAINT ck_routine_step_no CHECK (step_no BETWEEN 1 AND 12),
  CONSTRAINT ck_routine_step_category CHECK (category IN ('cleansing', 'prep', 'treatment', 'hydration',
                                                          'protection')),
  CONSTRAINT ck_routine_step_duration CHECK (duration_sec BETWEEN 5 AND 900)
);

CREATE TABLE daily_log (
  log_id    DOMAIN d_uuid
            DEFAULT LOWER(REGEXP_REPLACE(RAWTOHEX(SYS_GUID()),
                    '^(.{8})(.{4})(.{4})(.{4})(.{12})$', '\1-\2-\3-\4-\5')) NOT NULL,
  user_id   DOMAIN d_uuid NOT NULL,
  log_date  DATE NOT NULL,
  notes     VARCHAR2(2000 CHAR),
  CONSTRAINT pk_daily_log PRIMARY KEY (log_id),
  CONSTRAINT fk_daily_log_user FOREIGN KEY (user_id) REFERENCES app_user (user_id) ON DELETE CASCADE,
  -- o singură înregistrare pe zi și utilizator
  CONSTRAINT uq_daily_log_user_date UNIQUE (user_id, log_date),
  -- ziua calendaristică locală a utilizatorului, fără oră (DATE din Oracle păstrează și ora)
  CONSTRAINT ck_daily_log_day CHECK (log_date = TRUNC(log_date))
);

-- legătura 1:1 DOCUMENTS: cel mult o fotografie de progres pe zi (cheie străină unică)
CREATE TABLE progress_photo (
  photo_id  DOMAIN d_uuid NOT NULL,
  log_id    DOMAIN d_uuid NOT NULL,
  caption   VARCHAR2(140 CHAR),
  CONSTRAINT pk_progress_photo PRIMARY KEY (photo_id),
  CONSTRAINT fk_progress_photo_photo FOREIGN KEY (photo_id) REFERENCES photo (photo_id) ON DELETE CASCADE,
  CONSTRAINT fk_progress_photo_log FOREIGN KEY (log_id) REFERENCES daily_log (log_id) ON DELETE CASCADE,
  CONSTRAINT uq_progress_photo_log UNIQUE (log_id)
);

CREATE TABLE product_use (
  log_id      DOMAIN d_uuid NOT NULL,
  product_id  DOMAIN d_uuid NOT NULL,
  period      DOMAIN d_period NOT NULL,
  used_at     DOMAIN d_utc_ts DEFAULT FROM_TZ(SYS_EXTRACT_UTC(SYSTIMESTAMP), 'UTC') NOT NULL,
  CONSTRAINT pk_product_use PRIMARY KEY (log_id, product_id, period),
  CONSTRAINT fk_product_use_log FOREIGN KEY (log_id) REFERENCES daily_log (log_id) ON DELETE CASCADE,
  -- un produs bifat în jurnal nu poate fi șters
  CONSTRAINT fk_product_use_product FOREIGN KEY (product_id) REFERENCES product (product_id)
);

-- =====================================================================================
-- 4. Indecși. Oracle creează automat un index doar pentru PRIMARY KEY și UNIQUE, nu și pentru
--    cheile străine. O cheie străină fără index blochează tot tabelul copil când se șterge un
--    rând din părinte, de aceea fiecare cheie străină care nu este deja începutul unei chei
--    primare sau unice primește un index. Restul indecșilor urmează căile de acces ale aplicației.
-- =====================================================================================

-- chei străine
CREATE INDEX ix_one_time_token_user ON one_time_token (user_id);
CREATE INDEX ix_consent_user ON consent (user_id, consent_type);
CREATE INDEX ix_token_family_user ON token_family (user_id);
CREATE INDEX ix_refresh_token_family ON refresh_token (family_id);
CREATE INDEX ix_answer_option ON answer (question_id, option_value);
CREATE INDEX ix_zone_assessment_zone ON zone_assessment (zone_code);
CREATE INDEX ix_prediction_concern ON prediction (concern_code);
CREATE INDEX ix_analysis_photo_analysis ON analysis_photo (analysis_id);
CREATE INDEX ix_product_ingredient_ingr ON product_ingredient (ingredient_id);
CREATE INDEX ix_routine_source_analysis ON routine_source (analysis_id);
CREATE INDEX ix_routine_step_product ON routine_step (product_id);
CREATE INDEX ix_product_use_product ON product_use (product_id);

-- căi de acces: istoricul analizelor unui utilizator (cele mai noi primele), rutina curentă a
-- unei perioade, produsele cu un anumit marcaj, căutarea după categorie
CREATE INDEX ix_skin_analysis_user_created ON skin_analysis (user_id, created_at DESC);
CREATE INDEX ix_routine_user_period ON routine (user_id, period, created_at DESC);
CREATE INDEX ix_ingredient_flag_flag ON ingredient_flag (flag);
CREATE INDEX ix_product_category ON product (category);

-- ștergerea programată a jetoanelor expirate (echivalentul indecșilor TTL din MongoDB)
CREATE INDEX ix_refresh_token_expires ON refresh_token (expires_at);
CREATE INDEX ix_one_time_token_expires ON one_time_token (expires_at);

-- =====================================================================================
-- 5. Modificări de schemă (ALTER / DROP)
-- =====================================================================================

-- 5.1 O cheie străină adăugată după crearea tabelului: produsul unui pas de rutină.
--     ON DELETE SET NULL: dacă produsul dispare din catalog, pasul rămâne fără produs ales
ALTER TABLE routine_step
  ADD CONSTRAINT fk_routine_step_product FOREIGN KEY (product_id)
      REFERENCES product (product_id) ON DELETE SET NULL;

-- 5.2 Valoarea implicită a unei coloane existente (aceeași valoare, deci schema nu se schimbă)
ALTER TABLE app_user MODIFY (time_zone DEFAULT 'Europe/Bucharest');

-- 5.3 Dezactivarea și reactivarea unei constrângeri. ENABLE VALIDATE verifică din nou toate
--     rândurile existente, nu doar pe cele noi
ALTER TABLE reminder DISABLE CONSTRAINT ck_reminder_window;
ALTER TABLE reminder ENABLE VALIDATE CONSTRAINT ck_reminder_window;

-- 5.4 Adăugarea, redenumirea și ștergerea unei coloane, pe un tabel de lucru, ca schema v1
--     să rămână neschimbată
CREATE TABLE tmp_schema_demo (
  demo_id  NUMBER(5) NOT NULL,
  label    VARCHAR2(40 CHAR) NOT NULL,
  CONSTRAINT pk_tmp_schema_demo PRIMARY KEY (demo_id)
);

CREATE TABLE tmp_schema_demo_child (
  child_id  NUMBER(5) NOT NULL,
  demo_id   NUMBER(5) NOT NULL,
  CONSTRAINT pk_tmp_schema_demo_child PRIMARY KEY (child_id),
  CONSTRAINT fk_tmp_schema_demo_child FOREIGN KEY (demo_id) REFERENCES tmp_schema_demo (demo_id)
);

ALTER TABLE tmp_schema_demo ADD (note VARCHAR2(100 CHAR) DEFAULT 'n/a' NOT NULL);
ALTER TABLE tmp_schema_demo RENAME COLUMN note TO remark;
ALTER TABLE tmp_schema_demo MODIFY (remark DEFAULT 'none');
ALTER TABLE tmp_schema_demo DROP COLUMN remark;

-- 5.5 DROP TABLE fără CASCADE CONSTRAINTS eșuează cât timp o cheie străină indică spre tabel
--     (ORA-02449). Blocul PL/SQL prinde eroarea așteptată, ca scriptul să continue
BEGIN
  EXECUTE IMMEDIATE 'DROP TABLE tmp_schema_demo';
  RAISE_APPLICATION_ERROR(-20000, 'Eroare: DROP TABLE trebuia să fie refuzat');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -2449 THEN
      DBMS_OUTPUT.PUT_LINE('Așteptat: ORA-02449, tabelul este referit de o cheie străină.');
    ELSE
      RAISE;
    END IF;
END;
/

-- CASCADE CONSTRAINTS șterge întâi cheia străină din tabelul copil, apoi tabelul părinte
DROP TABLE tmp_schema_demo CASCADE CONSTRAINTS PURGE;
DROP TABLE tmp_schema_demo_child PURGE;

-- =====================================================================================
-- 6. Drepturi pentru SKINCARE_APP (privilegiul minim). Datele de referință (categorii, zone,
--    întrebări, produse, ingrediente) sunt doar citite de aplicație; datele utilizatorilor pot fi
--    citite și modificate. Pentru cele trei tabele de fotografii nu există INSERT direct:
--    fotografiile se adaugă doar prin pachetul photo_api (ziua a doua), care păstrează
--    specializarea totală. Numele se rezolvă în schema SKINCARE prin declanșatorul de conectare
--    din 00_users.sql.
-- =====================================================================================

-- date de referință: doar citire
GRANT SELECT ON skin_concern TO skincare_app;
GRANT SELECT ON face_zone TO skincare_app;
GRANT SELECT ON question TO skincare_app;
GRANT SELECT ON question_option TO skincare_app;
GRANT SELECT ON product TO skincare_app;
GRANT SELECT ON ingredient TO skincare_app;
GRANT SELECT ON product_ingredient TO skincare_app;
GRANT SELECT ON ingredient_function TO skincare_app;
GRANT SELECT ON ingredient_flag TO skincare_app;

-- datele utilizatorilor: citire și modificare
GRANT SELECT, INSERT, UPDATE, DELETE ON app_user TO skincare_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON one_time_token TO skincare_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON consent TO skincare_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON token_family TO skincare_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON refresh_token TO skincare_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON reminder TO skincare_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON skin_analysis TO skincare_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON answer TO skincare_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON zone_assessment TO skincare_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON prediction TO skincare_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON routine TO skincare_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON routine_source TO skincare_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON routine_step TO skincare_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON daily_log TO skincare_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON product_use TO skincare_app;

-- fotografii: fără INSERT (doar prin photo_api); harta Grad-CAM și descrierea pot fi completate
GRANT SELECT, DELETE ON photo TO skincare_app;
GRANT SELECT, UPDATE, DELETE ON analysis_photo TO skincare_app;
GRANT SELECT, UPDATE, DELETE ON progress_photo TO skincare_app;

-- =====================================================================================
-- 7. Comentarii păstrate în dicționarul bazei de date (USER_TAB_COMMENTS)
-- =====================================================================================
COMMENT ON TABLE app_user IS 'Contul utilizatorului (USER este cuvânt rezervat)';
COMMENT ON TABLE one_time_token IS 'Jetoane de unică folosință: verificarea adresei de e-mail și resetarea parolei';
COMMENT ON TABLE consent IS 'Consimțăminte acordate și retrase; dovada consimțământului (GDPR art. 7)';
COMMENT ON TABLE token_family IS 'O familie de jetoane de reîmprospătare pentru fiecare autentificare';
COMMENT ON TABLE refresh_token IS 'Jetoane de reîmprospătare rotite; se păstrează doar rezumatul SHA-256';
COMMENT ON TABLE reminder IS 'Mementouri pentru rutina de dimineață și de seară';
COMMENT ON TABLE skin_analysis IS 'O analiză a pielii: versiunea modelului și rezultatul serviciului ML';
COMMENT ON TABLE question IS 'Întrebările chestionarului (formularea SCIN)';
COMMENT ON TABLE question_option IS 'Variantele de răspuns ale fiecărei întrebări';
COMMENT ON TABLE answer IS 'Variantele bifate la o analiză; întrebările sărite nu au linii';
COMMENT ON TABLE face_zone IS 'Zonele feței folosite de harta pe zone';
COMMENT ON TABLE zone_assessment IS 'Observații pe zone ale feței (obiectiv suplimentar, poate rămâne gol)';
COMMENT ON TABLE skin_concern IS 'Cele patru categorii ale modelului';
COMMENT ON TABLE prediction IS 'Probabilitatea calibrată a fiecărei categorii într-o analiză';
COMMENT ON TABLE photo IS 'Superclasa fotografiilor: doar cheia obiectului, niciodată imaginea';
COMMENT ON TABLE analysis_photo IS 'Fotografie trimisă la o analiză (subclasă a PHOTO)';
COMMENT ON TABLE progress_photo IS 'Fotografie de progres din jurnalul zilnic (subclasă a PHOTO)';
COMMENT ON TABLE product IS 'Produse cosmetice (Open Beauty Facts sau introduse de autoare)';
COMMENT ON TABLE ingredient IS 'Ingrediente INCI cu explicație și scor 0-100';
COMMENT ON TABLE product_ingredient IS 'Lista INCI a unui produs, în ordinea de pe ambalaj';
COMMENT ON TABLE ingredient_function IS 'Funcțiile CosIng ale unui ingredient';
COMMENT ON TABLE ingredient_flag IS 'Marcajele de precauție ale unui ingredient';
COMMENT ON TABLE routine IS 'Rutină de dimineață sau de seară; cea mai nouă este rutina curentă';
COMMENT ON TABLE routine_source IS 'Analiza pe care se bazează o rutină (legătură opțională)';
COMMENT ON TABLE routine_step IS 'Pașii unei rutine (entitate slabă)';
COMMENT ON TABLE daily_log IS 'Jurnalul zilnic: o înregistrare pe zi și utilizator';
COMMENT ON TABLE product_use IS 'Produsele bifate într-o zi, dimineața sau seara';

-- =====================================================================================
-- 8. Verificare: 27 de tabele, niciun tabel de lucru rămas, nicio constrângere dezactivată
-- =====================================================================================
SELECT COUNT(*) AS tabele FROM user_tables;

SELECT constraint_type AS tip, COUNT(*) AS numar
  FROM user_constraints
 WHERE table_name NOT LIKE 'BIN$%'
 GROUP BY constraint_type
 ORDER BY constraint_type;

SELECT COUNT(*) AS constrangeri_dezactivate FROM user_constraints WHERE status <> 'ENABLED';

PROMPT Schema SKINCARE creată.
