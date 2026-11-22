-- =====================================================================================
-- Reguli de integritate în PL/SQL și aserțiuni SQL (Task O5)
-- Oracle AI Database 26ai Free, utilizatorul SKINCARE. Rulare după skincare.sql și înainte de seed.sql:
--   sql skincare@//localhost:1521/FREEPDB1 @db/oracle/plsql.sql
-- Scriptul este idempotent (CREATE OR REPLACE; aserțiunile se șterg întâi).
--
-- Coduri de eroare ridicate cu RAISE_APPLICATION_ERROR (intervalul -20000 ... -20999 este
-- rezervat erorilor definite de aplicație):
--   -20001  analiza nu există
--   -20002  ziua din jurnal nu există
--   -20003  analiza are deja 3 fotografii (limita din dicționarul de date)
--   -20004  rândul din subclasă nu corespunde cu PHOTO.photo_kind (specializare disjunctă)
--   -20005  photo_kind nu se poate schimba după creare
--   -20006  fotografia nu există
--   -20007  a doua cheie de reîmprospătare activă în aceeași familie
--   -20008  utilizatorul nu există
--
-- Secțiuni: 1 aserțiuni | 2 declanșatoare | 3 pachetul photo_api | 4 ștergerea contului |
--           5 exportul datelor unui utilizator (JSON) | 6 drepturi | 7 verificare
-- =====================================================================================

SET DEFINE OFF
SET SQLBLANKLINES ON
SET SERVEROUTPUT ON
WHENEVER SQLERROR EXIT FAILURE ROLLBACK

-- =====================================================================================
-- 1. Specializarea totală a lui PHOTO prin aserțiuni SQL (Oracle 23.26 / 26ai).
--    O aserțiune este o condiție asupra mai multor tabele pe care baza de date o verifică la
--    fiecare modificare. DEFERRABLE INITIALLY DEFERRED: verificarea se face la COMMIT, deci
--    rândul din PHOTO și rândul din subclasă se pot insera în două instrucțiuni ale aceleiași
--    tranzacții. Oracle nu are declanșatoare amânate, iar aserțiunea ține locul declanșatorului
--    amânat din proiectul PostgreSQL.
-- =====================================================================================
DROP ASSERTION IF EXISTS a_analysis_photo_total;
DROP ASSERTION IF EXISTS a_progress_photo_total;

-- fiecare fotografie de tip ANALYSIS are rândul ei în ANALYSIS_PHOTO
CREATE ASSERTION a_analysis_photo_total CHECK (
  NOT EXISTS (SELECT 1
                FROM photo p
               WHERE p.photo_kind = 'ANALYSIS'
                 AND NOT EXISTS (SELECT 1 FROM analysis_photo a WHERE a.photo_id = p.photo_id)))
  DEFERRABLE INITIALLY DEFERRED;

-- fiecare fotografie de tip PROGRESS are rândul ei în PROGRESS_PHOTO
CREATE ASSERTION a_progress_photo_total CHECK (
  NOT EXISTS (SELECT 1
                FROM photo p
               WHERE p.photo_kind = 'PROGRESS'
                 AND NOT EXISTS (SELECT 1 FROM progress_photo g WHERE g.photo_id = p.photo_id)))
  DEFERRABLE INITIALLY DEFERRED;

-- =====================================================================================
-- 2. Declanșatoare (triggere)
-- =====================================================================================

-- 2.1 Specializare disjunctă: un rând din ANALYSIS_PHOTO trebuie să indice o fotografie de tip
--     ANALYSIS. Declanșatorul citește PHOTO, nu tabelul pe care este definit, deci nu apare
--     eroarea de tabel în modificare (ORA-04091). Dacă fotografia lipsește, eroarea o dă cheia străină
CREATE OR REPLACE TRIGGER trg_analysis_photo_kind
  BEFORE INSERT OR UPDATE OF photo_id ON analysis_photo
  FOR EACH ROW
DECLARE
  v_kind photo.photo_kind%TYPE;
BEGIN
  SELECT photo_kind INTO v_kind FROM photo WHERE photo_id = :NEW.photo_id;
  IF v_kind <> 'ANALYSIS' THEN
    RAISE_APPLICATION_ERROR(-20004, 'Fotografia ' || :NEW.photo_id || ' este de tip ' || v_kind
                                    || ', nu ANALYSIS.');
  END IF;
EXCEPTION
  WHEN NO_DATA_FOUND THEN
    NULL;
END;
/

CREATE OR REPLACE TRIGGER trg_progress_photo_kind
  BEFORE INSERT OR UPDATE OF photo_id ON progress_photo
  FOR EACH ROW
DECLARE
  v_kind photo.photo_kind%TYPE;
BEGIN
  SELECT photo_kind INTO v_kind FROM photo WHERE photo_id = :NEW.photo_id;
  IF v_kind <> 'PROGRESS' THEN
    RAISE_APPLICATION_ERROR(-20004, 'Fotografia ' || :NEW.photo_id || ' este de tip ' || v_kind
                                    || ', nu PROGRESS.');
  END IF;
EXCEPTION
  WHEN NO_DATA_FOUND THEN
    NULL;
END;
/

-- 2.2 Tipul unei fotografii nu se mai schimbă după creare (altfel o fotografie ar putea trece
--     în cealaltă subclasă fără să-și schimbe rândul de subclasă)
CREATE OR REPLACE TRIGGER trg_photo_kind_fixed
  BEFORE UPDATE OF photo_kind ON photo
  FOR EACH ROW
  WHEN (NEW.photo_kind <> OLD.photo_kind)
BEGIN
  RAISE_APPLICATION_ERROR(-20005, 'photo_kind nu se poate schimba (' || :OLD.photo_kind || ' -> '
                                  || :NEW.photo_kind || ').');
END;
/

-- 2.3 Cel mult o cheie de reîmprospătare activă (revoked = FALSE) în fiecare familie.
--     Un declanșator pe rând nu poate număra rândurile propriului tabel (ORA-04091), de aceea se
--     folosește un declanșator compus: secțiunea AFTER EACH ROW reține familiile atinse, iar
--     secțiunea AFTER STATEMENT, care rulează după ce instrucțiunea a terminat, le verifică.
--     SELECT ... FOR UPDATE pe familie serializează două sesiuni care rotesc aceeași familie.
CREATE OR REPLACE TRIGGER trg_refresh_token_one_active
  FOR INSERT OR UPDATE OF revoked, family_id ON refresh_token
  COMPOUND TRIGGER

  TYPE t_family_ids IS TABLE OF refresh_token.family_id%TYPE;
  g_families t_family_ids := t_family_ids();

  AFTER EACH ROW IS
  BEGIN
    IF NOT :NEW.revoked THEN
      g_families.EXTEND;
      g_families(g_families.LAST) := :NEW.family_id;
    END IF;
  END AFTER EACH ROW;

  AFTER STATEMENT IS
    v_family token_family.family_id%TYPE;
    v_active PLS_INTEGER;
  BEGIN
    FOR i IN 1 .. g_families.COUNT LOOP
      SELECT family_id INTO v_family FROM token_family WHERE family_id = g_families(i) FOR UPDATE;
      SELECT COUNT(*) INTO v_active
        FROM refresh_token
       WHERE family_id = g_families(i) AND revoked = FALSE;
      IF v_active > 1 THEN
        RAISE_APPLICATION_ERROR(-20007, 'Familia ' || g_families(i) || ' ar avea ' || v_active
                                        || ' chei active; rotația revocă întâi cheia veche.');
      END IF;
    END LOOP;
  END AFTER STATEMENT;

END trg_refresh_token_one_active;
/

-- =====================================================================================
-- 3. Pachetul photo_api: singura cale prin care aplicația adaugă fotografii. Fiecare funcție scrie
--    rândul din PHOTO și rândul din subclasă în același apel, deci specializarea rămâne totală.
--    Pachetul rulează cu drepturile proprietarului (AUTHID DEFINER), astfel încât SKINCARE_APP
--    îl poate apela fără să aibă INSERT pe tabelele de fotografii. Nu face COMMIT: tranzacția
--    aparține apelantului (backend-ul).
-- =====================================================================================
CREATE OR REPLACE PACKAGE photo_api AUTHID DEFINER AS

  c_max_analysis_photos CONSTANT PLS_INTEGER := 3;

  -- adaugă o fotografie la o analiză și întoarce identificatorul ei
  FUNCTION add_analysis_photo(
    p_analysis_id  IN skin_analysis.analysis_id%TYPE,
    p_shot_type    IN analysis_photo.shot_type%TYPE,
    p_content_type IN photo.content_type%TYPE DEFAULT 'image/jpeg',
    p_heatmap_key  IN analysis_photo.heatmap_key%TYPE DEFAULT NULL
  ) RETURN photo.photo_id%TYPE;

  -- adaugă fotografia de progres a unei zile din jurnal
  FUNCTION add_progress_photo(
    p_log_id       IN daily_log.log_id%TYPE,
    p_caption      IN progress_photo.caption%TYPE DEFAULT NULL,
    p_content_type IN photo.content_type%TYPE DEFAULT 'image/jpeg'
  ) RETURN photo.photo_id%TYPE;

  -- șterge o fotografie; ștergerea în cascadă elimină și rândul din subclasă
  PROCEDURE delete_photo(p_photo_id IN photo.photo_id%TYPE);

  -- șterge o analiză împreună cu fotografiile ei (o ștergere simplă a analizei ar lăsa rândurile
  -- din PHOTO fără subclasă, iar aserțiunea ar refuza COMMIT-ul)
  PROCEDURE delete_analysis(p_analysis_id IN skin_analysis.analysis_id%TYPE);

END photo_api;
/

CREATE OR REPLACE PACKAGE BODY photo_api AS

  -- cheie nouă în formatul domeniului d_uuid (16 octeți aleatori din SYS_GUID, scriși 8-4-4-4-12)
  FUNCTION new_uuid RETURN photo.photo_id%TYPE IS
  BEGIN
    RETURN LOWER(REGEXP_REPLACE(RAWTOHEX(SYS_GUID()), '^(.{8})(.{4})(.{4})(.{4})(.{12})$',
                                '\1-\2-\3-\4-\5'));
  END new_uuid;

  FUNCTION add_analysis_photo(
    p_analysis_id  IN skin_analysis.analysis_id%TYPE,
    p_shot_type    IN analysis_photo.shot_type%TYPE,
    p_content_type IN photo.content_type%TYPE DEFAULT 'image/jpeg',
    p_heatmap_key  IN analysis_photo.heatmap_key%TYPE DEFAULT NULL
  ) RETURN photo.photo_id%TYPE IS
    v_id     photo.photo_id%TYPE := new_uuid;
    v_lock   skin_analysis.analysis_id%TYPE;
    v_photos PLS_INTEGER;
  BEGIN
    -- blocarea analizei împiedică două apeluri simultane să treacă amândouă de limita de 3
    BEGIN
      SELECT analysis_id INTO v_lock FROM skin_analysis WHERE analysis_id = p_analysis_id FOR UPDATE;
    EXCEPTION
      WHEN NO_DATA_FOUND THEN
        RAISE_APPLICATION_ERROR(-20001, 'Analiza ' || p_analysis_id || ' nu există.');
    END;
    SELECT COUNT(*) INTO v_photos FROM analysis_photo WHERE analysis_id = p_analysis_id;
    IF v_photos >= c_max_analysis_photos THEN
      RAISE_APPLICATION_ERROR(-20003, 'Analiza ' || p_analysis_id || ' are deja '
                                      || c_max_analysis_photos || ' fotografii.');
    END IF;
    INSERT INTO photo (photo_id, object_key, content_type, photo_kind)
    VALUES (v_id, 'photos/' || v_id, p_content_type, 'ANALYSIS');
    INSERT INTO analysis_photo (photo_id, analysis_id, shot_type, heatmap_key)
    VALUES (v_id, p_analysis_id, p_shot_type, p_heatmap_key);
    RETURN v_id;
  END add_analysis_photo;

  FUNCTION add_progress_photo(
    p_log_id       IN daily_log.log_id%TYPE,
    p_caption      IN progress_photo.caption%TYPE DEFAULT NULL,
    p_content_type IN photo.content_type%TYPE DEFAULT 'image/jpeg'
  ) RETURN photo.photo_id%TYPE IS
    v_id   photo.photo_id%TYPE := new_uuid;
    v_lock daily_log.log_id%TYPE;
  BEGIN
    BEGIN
      SELECT log_id INTO v_lock FROM daily_log WHERE log_id = p_log_id FOR UPDATE;
    EXCEPTION
      WHEN NO_DATA_FOUND THEN
        RAISE_APPLICATION_ERROR(-20002, 'Ziua din jurnal ' || p_log_id || ' nu există.');
    END;
    INSERT INTO photo (photo_id, object_key, content_type, photo_kind)
    VALUES (v_id, 'photos/' || v_id, p_content_type, 'PROGRESS');
    -- a doua fotografie în aceeași zi încalcă uq_progress_photo_log (ORA-00001)
    INSERT INTO progress_photo (photo_id, log_id, caption) VALUES (v_id, p_log_id, p_caption);
    RETURN v_id;
  END add_progress_photo;

  PROCEDURE delete_photo(p_photo_id IN photo.photo_id%TYPE) IS
  BEGIN
    DELETE FROM photo WHERE photo_id = p_photo_id;
    IF SQL%ROWCOUNT = 0 THEN
      RAISE_APPLICATION_ERROR(-20006, 'Fotografia ' || p_photo_id || ' nu există.');
    END IF;
  END delete_photo;

  PROCEDURE delete_analysis(p_analysis_id IN skin_analysis.analysis_id%TYPE) IS
  BEGIN
    DELETE FROM photo
     WHERE photo_id IN (SELECT photo_id FROM analysis_photo WHERE analysis_id = p_analysis_id);
    DELETE FROM skin_analysis WHERE analysis_id = p_analysis_id;
    IF SQL%ROWCOUNT = 0 THEN
      RAISE_APPLICATION_ERROR(-20001, 'Analiza ' || p_analysis_id || ' nu există.');
    END IF;
  END delete_analysis;

END photo_api;
/

-- =====================================================================================
-- 4. Ștergerea contului (dreptul la ștergere, GDPR art. 17). ON DELETE CASCADE șterge toate
--    rândurile utilizatorului, dar PHOTO nu are cheie străină spre utilizator: fotografiile se
--    șterg întâi, apoi contul. Marcajul deletion_requested_at se scrie la început, ca un job
--    întrerupt să poată fi reluat. Întoarce numărul de fotografii șterse; backend-ul citește
--    înainte cheile lor (object_key) ca să șteargă și fișierele din depozitul de obiecte.
--    Nu face COMMIT.
-- =====================================================================================
CREATE OR REPLACE FUNCTION erase_user(p_user_id IN app_user.user_id%TYPE) RETURN PLS_INTEGER
  AUTHID DEFINER
IS
  v_photos PLS_INTEGER;
BEGIN
  UPDATE app_user
     SET deletion_requested_at = NVL(deletion_requested_at, FROM_TZ(SYS_EXTRACT_UTC(SYSTIMESTAMP), 'UTC'))
   WHERE user_id = p_user_id;
  IF SQL%ROWCOUNT = 0 THEN
    RAISE_APPLICATION_ERROR(-20008, 'Utilizatorul ' || p_user_id || ' nu există.');
  END IF;
  DELETE FROM photo
   WHERE photo_id IN (SELECT ap.photo_id
                        FROM analysis_photo ap JOIN skin_analysis a ON a.analysis_id = ap.analysis_id
                       WHERE a.user_id = p_user_id
                      UNION ALL
                      SELECT pp.photo_id
                        FROM progress_photo pp JOIN daily_log l ON l.log_id = pp.log_id
                       WHERE l.user_id = p_user_id);
  v_photos := SQL%ROWCOUNT;
  DELETE FROM app_user WHERE user_id = p_user_id;
  RETURN v_photos;
END erase_user;
/

-- =====================================================================================
-- 5. Exportul datelor unui utilizator (dreptul de acces și portabilitatea, GDPR art. 15 și 20),
--    un singur document JSON construit cu JSON_OBJECT și JSON_ARRAYAGG. Nu conține rezumatul
--    parolei și nici rezumatele jetoanelor (date de securitate, nu date despre persoană).
--    COALESCE(..., TO_CLOB('[]')) pune o listă goală în loc de null; FORMAT JSON spune că valoarea
--    subinterogării este deja JSON și nu trebuie pusă între ghilimele.
-- =====================================================================================
CREATE OR REPLACE FUNCTION export_user_json(p_user_id IN app_user.user_id%TYPE) RETURN CLOB
  AUTHID DEFINER
IS
  v_doc CLOB;
BEGIN
  SELECT JSON_OBJECT(
           'exported_at' VALUE FROM_TZ(SYS_EXTRACT_UTC(SYSTIMESTAMP), 'UTC'),
           'user' VALUE JSON_OBJECT(
             'user_id' VALUE u.user_id, 'email' VALUE u.email, 'first_name' VALUE u.first_name,
             'last_name' VALUE u.last_name, 'date_of_birth' VALUE TO_CHAR(u.date_of_birth, 'YYYY-MM-DD'),
             'skin_type' VALUE u.skin_type, 'main_concern' VALUE u.main_concern, 'climate' VALUE u.climate,
             'language' VALUE u.language, 'time_zone' VALUE u.time_zone, 'created_at' VALUE u.created_at,
             'email_verified_at' VALUE u.email_verified_at),
           'consents' VALUE COALESCE((
             SELECT JSON_ARRAYAGG(JSON_OBJECT('consent_type' VALUE c.consent_type,
                                              'policy_version' VALUE c.policy_version,
                                              'granted_at' VALUE c.granted_at,
                                              'withdrawn_at' VALUE c.withdrawn_at)
                                  ORDER BY c.granted_at, c.consent_type RETURNING CLOB)
               FROM consent c WHERE c.user_id = u.user_id), TO_CLOB('[]')) FORMAT JSON,
           'reminders' VALUE COALESCE((
             SELECT JSON_ARRAYAGG(JSON_OBJECT('period' VALUE r.period, 'time_of_day' VALUE r.time_of_day,
                                              'enabled' VALUE r.enabled)
                                  ORDER BY r.period RETURNING CLOB)
               FROM reminder r WHERE r.user_id = u.user_id), TO_CLOB('[]')) FORMAT JSON,
           'analyses' VALUE COALESCE((
             SELECT JSON_ARRAYAGG(JSON_OBJECT(
                      'analysis_id' VALUE a.analysis_id, 'created_at' VALUE a.created_at,
                      'model_version' VALUE a.model_version, 'status' VALUE a.status,
                      'ood_score' VALUE a.ood_score,
                      'predictions' VALUE COALESCE((
                        SELECT JSON_ARRAYAGG(JSON_OBJECT('concern_code' VALUE p.concern_code,
                                                         'probability' VALUE p.probability)
                                             ORDER BY p.probability DESC RETURNING CLOB)
                          FROM prediction p WHERE p.analysis_id = a.analysis_id), TO_CLOB('[]')) FORMAT JSON,
                      'answers' VALUE COALESCE((
                        SELECT JSON_ARRAYAGG(JSON_OBJECT('question' VALUE q.field_key,
                                                         'option' VALUE an.option_value)
                                             ORDER BY q.question_id, an.option_value RETURNING CLOB)
                          FROM answer an JOIN question q ON q.question_id = an.question_id
                         WHERE an.analysis_id = a.analysis_id), TO_CLOB('[]')) FORMAT JSON,
                      'photos' VALUE COALESCE((
                        SELECT JSON_ARRAYAGG(JSON_OBJECT('object_key' VALUE ph.object_key,
                                                         'shot_type' VALUE ap.shot_type,
                                                         'heatmap_key' VALUE ap.heatmap_key)
                                             ORDER BY ap.shot_type RETURNING CLOB)
                          FROM analysis_photo ap JOIN photo ph ON ph.photo_id = ap.photo_id
                         WHERE ap.analysis_id = a.analysis_id), TO_CLOB('[]')) FORMAT JSON
                      RETURNING CLOB)
                    ORDER BY a.created_at RETURNING CLOB)
               FROM skin_analysis a WHERE a.user_id = u.user_id), TO_CLOB('[]')) FORMAT JSON,
           'routines' VALUE COALESCE((
             SELECT JSON_ARRAYAGG(JSON_OBJECT(
                      'routine_id' VALUE ro.routine_id, 'period' VALUE ro.period,
                      'complexity_level' VALUE ro.complexity_level, 'created_at' VALUE ro.created_at,
                      'source_analysis_id' VALUE (SELECT rs.analysis_id FROM routine_source rs
                                                   WHERE rs.routine_id = ro.routine_id),
                      'steps' VALUE COALESCE((
                        SELECT JSON_ARRAYAGG(JSON_OBJECT('step_no' VALUE st.step_no, 'category' VALUE st.category,
                                                         'product' VALUE pr.name, 'instruction' VALUE st.instruction,
                                                         'duration_sec' VALUE st.duration_sec)
                                             ORDER BY st.step_no RETURNING CLOB)
                          FROM routine_step st LEFT JOIN product pr ON pr.product_id = st.product_id
                         WHERE st.routine_id = ro.routine_id), TO_CLOB('[]')) FORMAT JSON
                      RETURNING CLOB)
                    ORDER BY ro.created_at RETURNING CLOB)
               FROM routine ro WHERE ro.user_id = u.user_id), TO_CLOB('[]')) FORMAT JSON,
           'daily_logs' VALUE COALESCE((
             SELECT JSON_ARRAYAGG(JSON_OBJECT(
                      'log_date' VALUE TO_CHAR(l.log_date, 'YYYY-MM-DD'), 'notes' VALUE l.notes,
                      'products_used' VALUE COALESCE((
                        SELECT JSON_ARRAYAGG(JSON_OBJECT('period' VALUE pu.period, 'product' VALUE pr.name,
                                                         'used_at' VALUE pu.used_at)
                                             ORDER BY pu.used_at RETURNING CLOB)
                          FROM product_use pu JOIN product pr ON pr.product_id = pu.product_id
                         WHERE pu.log_id = l.log_id), TO_CLOB('[]')) FORMAT JSON,
                      'progress_photo' VALUE (SELECT ph.object_key FROM progress_photo pp
                                                JOIN photo ph ON ph.photo_id = pp.photo_id
                                               WHERE pp.log_id = l.log_id)
                      RETURNING CLOB)
                    ORDER BY l.log_date RETURNING CLOB)
               FROM daily_log l WHERE l.user_id = u.user_id), TO_CLOB('[]')) FORMAT JSON
           RETURNING CLOB)
    INTO v_doc
    FROM app_user u
   WHERE u.user_id = p_user_id;
  RETURN v_doc;
EXCEPTION
  WHEN NO_DATA_FOUND THEN
    RAISE_APPLICATION_ERROR(-20008, 'Utilizatorul ' || p_user_id || ' nu există.');
END export_user_json;
/

-- =====================================================================================
-- 6. Drepturi pentru SKINCARE_APP: poate apela pachetul și cele două funcții, dar tot nu poate
--    insera direct în tabelele de fotografii
-- =====================================================================================
GRANT EXECUTE ON photo_api TO skincare_app;
GRANT EXECUTE ON erase_user TO skincare_app;
GRANT EXECUTE ON export_user_json TO skincare_app;

-- =====================================================================================
-- 7. Verificare: niciun obiect PL/SQL invalid, aserțiunile și declanșatoarele există
-- =====================================================================================
SELECT object_type AS tip, object_name AS nume, status
  FROM user_objects
 WHERE object_type IN ('PACKAGE', 'PACKAGE BODY', 'FUNCTION', 'TRIGGER')
 ORDER BY object_type, object_name;

SELECT COUNT(*) AS obiecte_invalide FROM user_objects WHERE status <> 'VALID';

-- o eroare de compilare apare în SQL*Plus doar ca avertisment; blocul oprește scriptul
DECLARE
  v_invalid PLS_INTEGER;
BEGIN
  SELECT COUNT(*) INTO v_invalid FROM user_objects WHERE status <> 'VALID';
  IF v_invalid > 0 THEN
    RAISE_APPLICATION_ERROR(-20000, v_invalid || ' obiecte PL/SQL invalide (vezi USER_ERRORS).');
  END IF;
END;
/

SELECT assertion_name AS asertiune FROM user_assertions ORDER BY assertion_name;

PROMPT Reguli PL/SQL create.
