-- =====================================================================================
-- Modificarea datelor și tranzacții (Task O6)
-- Oracle AI Database 26ai Free. Rulare după seed.sql, conectat ca SKINCARE, cu doi parametri
-- (parola lui SKINCARE_APP și șirul de conectare, pentru secțiunea 7):
--   sql skincare@//localhost:1521/FREEPDB1 @db/oracle/dml.sql <parola_app> //localhost:1521/FREEPDB1
--
-- Toate modificările se fac pe un utilizator de test creat aici, care este șters la sfârșit
-- prin funcția erase_user. Datele de test comune rămân exact cum le-a încărcat seed.sql, deci
-- interogările din queries.sql dau aceleași rezultate după rularea acestui script.
-- Instrucțiunile care trebuie să eșueze sunt puse în blocuri BEGIN ... EXCEPTION ... END care
-- afișează eroarea așteptată; orice altă eroare oprește scriptul (WHENEVER SQLERROR).
--
-- Secțiuni: 0 pregătire | 1 INSERT | 2 UPDATE | 3 DELETE și MERGE | 4 fotografii prin photo_api |
--           5 instrucțiuni care trebuie să eșueze | 6 tranzacții | 7 utilizatorul aplicației și
--           ștergerea contului | 8 verificare
-- =====================================================================================

SET SQLBLANKLINES ON
SET SERVEROUTPUT ON
SET VERIFY OFF
SET FEEDBACK ON
WHENEVER SQLERROR EXIT FAILURE ROLLBACK

-- identificatorii datelor de test (variabile de substituție SQL*Plus, înlocuite înainte de execuție)
DEFINE demo_user     = 0d000000-0000-4000-8000-000000000001
DEFINE demo_analysis = 0d000000-0000-4000-8000-0000000000a1
DEFINE demo_routine  = 0d000000-0000-4000-8000-0000000000b1
DEFINE demo_family   = 0d000000-0000-4000-8000-0000000000d1
DEFINE demo_token_1  = 0d000000-0000-4000-8000-0000000000e1
DEFINE demo_token_2  = 0d000000-0000-4000-8000-0000000000e2
DEFINE demo_token_3  = 0d000000-0000-4000-8000-0000000000e3
-- rutina de dimineață a unui utilizator din datele de test, folosită ca model în 1.4
DEFINE ana_am_routine = 1c4091b8-b058-52bc-8e69-4129ef46b748

-- =====================================================================================
-- 0. Pregătire: dacă o rulare anterioară s-a oprit la jumătate, utilizatorul de test se șterge
-- =====================================================================================
DECLARE
  v_photos PLS_INTEGER;
BEGIN
  v_photos := erase_user('&demo_user');
  DBMS_OUTPUT.PUT_LINE('Utilizator de test rămas dintr-o rulare anterioară, șters.');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -20008 THEN
      NULL;
    ELSE
      RAISE;
    END IF;
END;
/
COMMIT;

-- =====================================================================================
-- 1. INSERT
-- =====================================================================================

-- 1.1 Un singur rând. Coloanele omise primesc valoarea implicită: language ('ro'),
--     time_zone ('Europe/Bucharest'), failed_logins (0). created_at este dat explicit (nu ora
--     curentă), ca momentele din exemplele următoare să fie după crearea contului
INSERT INTO app_user (user_id, email, password_hash, first_name, last_name, date_of_birth,
                      skin_type, main_concern, climate, created_at)
VALUES ('&demo_user', 'test.dml@example.com',
        '$argon2id$v=19$m=65536,t=3,p=4$ZGVtb3NhbHQ$ZGVtb2hhc2hkZW1vaGFzaA', 'Test', 'Demo',
        DATE '1998-05-14', 'combination', 'acne', 'temperate', TIMESTAMP '2026-11-20 07:55:00 +00:00');

-- 1.2 Mai multe rânduri în mai multe tabele dintr-o singură instrucțiune (INSERT ALL):
--     cele două mementouri și consimțămintele obligatorii. Cheile lipsesc, deci se generează
INSERT ALL
  INTO reminder (user_id, period, time_of_day, enabled) VALUES ('&demo_user', 'AM', '07:30', TRUE)
  INTO reminder (user_id, period, time_of_day, enabled) VALUES ('&demo_user', 'PM', '21:00', TRUE)
  INTO consent (user_id, consent_type, policy_version) VALUES ('&demo_user', 'privacy_policy', '1.0')
  INTO consent (user_id, consent_type, policy_version) VALUES ('&demo_user', 'photo_processing', '1.0')
  INTO consent (user_id, consent_type, policy_version) VALUES ('&demo_user', 'health_data', '1.0')
SELECT * FROM dual;

-- 1.3 O analiză cu cele patru probabilități (mai multe rânduri într-un singur VALUES, 23ai) și
--     răspunsurile la chestionar
INSERT INTO skin_analysis (analysis_id, user_id, model_version, status, ood_score)
VALUES ('&demo_analysis', '&demo_user', 'skin_concern_dinov2@6ed60809e644c604', 'answered', 0.3050);

INSERT INTO prediction (analysis_id, concern_code, probability) VALUES
  ('&demo_analysis', 'acne', 0.6400),
  ('&demo_analysis', 'eczema_dermatitis', 0.1100),
  ('&demo_analysis', 'redness_rosacea', 0.1500),
  ('&demo_analysis', 'normal_other', 0.1000);

INSERT INTO answer (analysis_id, question_id, option_value) VALUES
  ('&demo_analysis', 1, 'AGE_18_TO_29'),
  ('&demo_analysis', 2, 'head_or_neck'),
  ('&demo_analysis', 3, 'itching'),
  ('&demo_analysis', 3, 'burning');

-- 1.4 INSERT ... SELECT: o rutină nouă, bazată pe analiză, cu pașii copiați din rutina de
--     dimineață a altui utilizator
INSERT INTO routine (routine_id, user_id, period, complexity_level)
VALUES ('&demo_routine', '&demo_user', 'AM', 'advanced');

INSERT INTO routine_source (routine_id, analysis_id) VALUES ('&demo_routine', '&demo_analysis');

INSERT INTO routine_step (routine_id, step_no, product_id, category, instruction, duration_sec)
SELECT '&demo_routine', step_no, product_id, category, instruction, duration_sec
  FROM routine_step
 WHERE routine_id = '&ana_am_routine';

-- 1.5 Un jeton de verificare a adresei de e-mail, folosit după 5 minute
INSERT INTO one_time_token (user_id, purpose, token_hash, created_at, expires_at, used_at)
VALUES ('&demo_user', 'email_verification', LOWER(RAWTOHEX(STANDARD_HASH('demo-verify', 'SHA256'))),
        TIMESTAMP '2026-11-20 08:00:00 +00:00', TIMESTAMP '2026-11-21 08:00:00 +00:00',
        TIMESTAMP '2026-11-20 08:05:00 +00:00');

COMMIT;

-- =====================================================================================
-- 2. UPDATE
-- =====================================================================================

-- 2.1 Cu subinterogare și CASE: nivelul rutinei se recalculează din numărul de pași
--     (3 pași = basic, 5-6 = intermediate, 7 sau mai mulți = advanced)
UPDATE routine r
   SET complexity_level = (SELECT CASE
                                    WHEN COUNT(*) >= 7 THEN 'advanced'
                                    WHEN COUNT(*) >= 5 THEN 'intermediate'
                                    ELSE 'basic'
                                  END
                             FROM routine_step s
                            WHERE s.routine_id = r.routine_id)
 WHERE r.user_id = '&demo_user';

-- 2.2 Cu CASE: ora mementourilor se mută cu o jumătate de oră, diferit pentru dimineață și seară
UPDATE reminder
   SET time_of_day = CASE period WHEN 'AM' THEN '07:00' ELSE '21:30' END
 WHERE user_id = '&demo_user';

-- 2.3 Cu subinterogare corelată în SET și în WHERE: adresa de e-mail devine verificată la
--     momentul în care a fost folosit jetonul de verificare
UPDATE app_user u
   SET email_verified_at = (SELECT MAX(t.used_at)
                              FROM one_time_token t
                             WHERE t.user_id = u.user_id AND t.purpose = 'email_verification')
 WHERE u.email_verified_at IS NULL
   AND u.user_id = '&demo_user'
   AND EXISTS (SELECT 1
                 FROM one_time_token t
                WHERE t.user_id = u.user_id AND t.purpose = 'email_verification' AND t.used_at IS NOT NULL);

SELECT complexity_level, (SELECT COUNT(*) FROM routine_step WHERE routine_id = '&demo_routine') AS pasi
  FROM routine WHERE routine_id = '&demo_routine';

COMMIT;

-- =====================================================================================
-- 3. MERGE și DELETE
-- =====================================================================================

-- 3.1 MERGE ca „upsert” pentru jurnalul zilnic: dacă ziua există se actualizează nota, altfel
--     se inserează. Rulat de două ori: prima dată inserează, a doua oară actualizează
MERGE INTO daily_log d
USING (SELECT '&demo_user' AS user_id, DATE '2026-11-20' AS log_date, 'Prima notă.' AS notes FROM dual) s
   ON (d.user_id = s.user_id AND d.log_date = s.log_date)
 WHEN MATCHED THEN UPDATE SET d.notes = s.notes
 WHEN NOT MATCHED THEN INSERT (user_id, log_date, notes) VALUES (s.user_id, s.log_date, s.notes);

MERGE INTO daily_log d
USING (SELECT '&demo_user' AS user_id, DATE '2026-11-20' AS log_date, 'Notă corectată.' AS notes FROM dual) s
   ON (d.user_id = s.user_id AND d.log_date = s.log_date)
 WHEN MATCHED THEN UPDATE SET d.notes = s.notes
 WHEN NOT MATCHED THEN INSERT (user_id, log_date, notes) VALUES (s.user_id, s.log_date, s.notes);

-- produsele bifate în acea zi: toate produsele rutinei, plus o mască
INSERT INTO product_use (log_id, product_id, period)
SELECT l.log_id, s.product_id, 'AM'
  FROM daily_log l JOIN routine_step s ON s.routine_id = '&demo_routine'
 WHERE l.user_id = '&demo_user' AND l.log_date = DATE '2026-11-20' AND s.product_id IS NOT NULL;

INSERT INTO product_use (log_id, product_id, period)
SELECT l.log_id, p.product_id, 'PM'
  FROM daily_log l CROSS JOIN product p
 WHERE l.user_id = '&demo_user' AND l.log_date = DATE '2026-11-20' AND p.category = 'mask'
 FETCH FIRST 1 ROW ONLY;

-- 3.2 DELETE cu subinterogări: se scot din jurnalul utilizatorului măștile bifate
DELETE FROM product_use
 WHERE log_id IN (SELECT log_id FROM daily_log WHERE user_id = '&demo_user')
   AND product_id IN (SELECT product_id FROM product WHERE category = 'mask');

SELECT notes, (SELECT COUNT(*) FROM product_use pu WHERE pu.log_id = l.log_id) AS produse_bifate
  FROM daily_log l WHERE user_id = '&demo_user';

COMMIT;

-- =====================================================================================
-- 4. Fotografii prin pachetul photo_api (PHOTO și subclasa sunt scrise împreună)
-- =====================================================================================
DECLARE
  v_photo photo.photo_id%TYPE;
  v_log   daily_log.log_id%TYPE;
BEGIN
  v_photo := photo_api.add_analysis_photo('&demo_analysis', 'front');
  v_photo := photo_api.add_analysis_photo('&demo_analysis', 'left');
  v_photo := photo_api.add_analysis_photo('&demo_analysis', 'right');
  SELECT log_id INTO v_log FROM daily_log WHERE user_id = '&demo_user' AND log_date = DATE '2026-11-20';
  v_photo := photo_api.add_progress_photo(v_log, 'Prima săptămână');
  DBMS_OUTPUT.PUT_LINE('Fotografii adăugate prin photo_api: 3 la analiză, 1 de progres.');
END;
/
COMMIT;

-- =====================================================================================
-- 5. Instrucțiuni care trebuie să eșueze. Fiecare bloc acceptă doar codul de eroare așteptat
--    și se oprește cu -20000 dacă instrucțiunea reușește
-- =====================================================================================

-- 5.1 Adresă de e-mail duplicată: ORA-00001 (uq_app_user_email)
BEGIN
  INSERT INTO app_user (email, password_hash, first_name, last_name, date_of_birth, skin_type,
                        main_concern, climate)
  VALUES ('ana.popescu@example.com', '$argon2id$v=19$m=65536,t=3,p=4$eA$eA', 'Ana', 'Copie',
          DATE '2000-01-01', 'dry', 'none', 'cold');
  RAISE_APPLICATION_ERROR(-20000, 'Eroare: INSERT trebuia refuzat');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -1 THEN DBMS_OUTPUT.PUT_LINE('5.1 așteptat: ' || SQLERRM); ELSE RAISE; END IF;
END;
/

-- 5.2 Probabilitate 1.2: regula domeniului d_probability (0-1)
BEGIN
  UPDATE prediction SET probability = 1.2
   WHERE analysis_id = '&demo_analysis' AND concern_code = 'acne';
  RAISE_APPLICATION_ERROR(-20000, 'Eroare: UPDATE trebuia refuzat');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE IN (-2290, -11534) THEN DBMS_OUTPUT.PUT_LINE('5.2 așteptat: ' || SQLERRM); ELSE RAISE; END IF;
END;
/

-- 5.3 A doua înregistrare în jurnal în aceeași zi: ORA-00001 (uq_daily_log_user_date)
BEGIN
  INSERT INTO daily_log (user_id, log_date) VALUES ('&demo_user', DATE '2026-11-20');
  RAISE_APPLICATION_ERROR(-20000, 'Eroare: INSERT trebuia refuzat');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -1 THEN DBMS_OUTPUT.PUT_LINE('5.3 așteptat: ' || SQLERRM); ELSE RAISE; END IF;
END;
/

-- 5.4 Ștergerea unui ingredient folosit de un produs: ORA-02292 (cheie străină fără acțiune)
BEGIN
  DELETE FROM ingredient WHERE inci_name = 'AQUA';
  RAISE_APPLICATION_ERROR(-20000, 'Eroare: DELETE trebuia refuzat');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -2292 THEN DBMS_OUTPUT.PUT_LINE('5.4 așteptat: ' || SQLERRM); ELSE RAISE; END IF;
END;
/

-- 5.5 Utilizator sub 18 ani: ORA-02290 (ck_app_user_adult)
BEGIN
  INSERT INTO app_user (email, password_hash, first_name, last_name, date_of_birth, skin_type,
                        main_concern, climate)
  VALUES ('minor@example.com', '$argon2id$v=19$m=65536,t=3,p=4$eA$eA', 'Minor', 'Test',
          ADD_MONTHS(TRUNC(SYSDATE), -12 * 16), 'normal', 'none', 'temperate');
  RAISE_APPLICATION_ERROR(-20000, 'Eroare: INSERT trebuia refuzat');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -2290 THEN DBMS_OUTPUT.PUT_LINE('5.5 așteptat: ' || SQLERRM); ELSE RAISE; END IF;
END;
/

-- 5.6 A patra fotografie la aceeași analiză: -20003 din photo_api
DECLARE
  v_photo photo.photo_id%TYPE;
BEGIN
  v_photo := photo_api.add_analysis_photo('&demo_analysis', 'front');
  RAISE_APPLICATION_ERROR(-20000, 'Eroare: a patra fotografie trebuia refuzată');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -20003 THEN DBMS_OUTPUT.PUT_LINE('5.6 așteptat: ' || SQLERRM); ELSE RAISE; END IF;
END;
/

-- 5.7 Specializare disjunctă: o fotografie PROGRESS pusă în ANALYSIS_PHOTO: -20004 din declanșator
BEGIN
  INSERT INTO photo (photo_id, object_key, content_type, photo_kind)
  VALUES ('0d000000-0000-4000-8000-0000000000f1', 'photos/0d000000-0000-4000-8000-0000000000f1',
          'image/jpeg', 'PROGRESS');
  INSERT INTO analysis_photo (photo_id, analysis_id, shot_type)
  VALUES ('0d000000-0000-4000-8000-0000000000f1', '&demo_analysis', 'front');
  RAISE_APPLICATION_ERROR(-20000, 'Eroare: INSERT trebuia refuzat');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -20004 THEN DBMS_OUTPUT.PUT_LINE('5.7 așteptat: ' || SQLERRM); ELSE RAISE; END IF;
END;
/
-- rândul din PHOTO inserat în blocul de mai sus nu are subclasă: se anulează
ROLLBACK;

-- 5.8 Specializare totală: o fotografie fără rând în subclasă este refuzată la COMMIT de
--     aserțiunea a_analysis_photo_total (ORA-02091 tranzacție anulată, cauza ORA-08601)
BEGIN
  INSERT INTO photo (photo_id, object_key, content_type, photo_kind)
  VALUES ('0d000000-0000-4000-8000-0000000000f2', 'photos/0d000000-0000-4000-8000-0000000000f2',
          'image/jpeg', 'ANALYSIS');
  COMMIT;
  RAISE_APPLICATION_ERROR(-20000, 'Eroare: COMMIT trebuia refuzat');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE IN (-2091, -8601) THEN DBMS_OUTPUT.PUT_LINE('5.8 așteptat: ' || SQLERRM); ELSE RAISE; END IF;
END;
/

-- 5.9 Tipul unei fotografii nu se schimbă: -20005 din declanșator
BEGIN
  UPDATE photo SET photo_kind = 'PROGRESS'
   WHERE photo_id = (SELECT photo_id FROM analysis_photo WHERE analysis_id = '&demo_analysis'
                      FETCH FIRST 1 ROW ONLY);
  RAISE_APPLICATION_ERROR(-20000, 'Eroare: UPDATE trebuia refuzat');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -20005 THEN DBMS_OUTPUT.PUT_LINE('5.9 așteptat: ' || SQLERRM); ELSE RAISE; END IF;
END;
/

-- =====================================================================================
-- 6. Tranzacții
-- =====================================================================================

-- 6.1 O sesiune nouă (familie de jetoane) cu prima cheie de reîmprospătare
INSERT INTO token_family (family_id, user_id) VALUES ('&demo_family', '&demo_user');
INSERT INTO refresh_token (token_id, family_id, token_hash, expires_at)
VALUES ('&demo_token_1', '&demo_family', LOWER(RAWTOHEX(STANDARD_HASH('demo-refresh-1', 'SHA256'))),
        FROM_TZ(SYS_EXTRACT_UTC(SYSTIMESTAMP), 'UTC') + INTERVAL '30' DAY);
COMMIT;

-- 6.2 Rotație în ordinea greșită (cheia nouă înainte de revocarea celei vechi): -20007 din
--     declanșatorul compus, iar cheia veche rămâne singura activă
BEGIN
  INSERT INTO refresh_token (token_id, family_id, token_hash, expires_at)
  VALUES ('&demo_token_2', '&demo_family', LOWER(RAWTOHEX(STANDARD_HASH('demo-refresh-2', 'SHA256'))),
          FROM_TZ(SYS_EXTRACT_UTC(SYSTIMESTAMP), 'UTC') + INTERVAL '30' DAY);
  RAISE_APPLICATION_ERROR(-20000, 'Eroare: a doua cheie activă trebuia refuzată');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -20007 THEN DBMS_OUTPUT.PUT_LINE('6.2 așteptat: ' || SQLERRM); ELSE RAISE; END IF;
END;
/

-- 6.3 Rotația corectă, ca o singură tranzacție: cheia veche se revocă, cheia nouă se inserează,
--     apoi COMMIT. Dacă una dintre instrucțiuni eșuează, nu rămâne niciuna
UPDATE refresh_token SET revoked = TRUE WHERE token_id = '&demo_token_1';
INSERT INTO refresh_token (token_id, family_id, token_hash, expires_at)
VALUES ('&demo_token_2', '&demo_family', LOWER(RAWTOHEX(STANDARD_HASH('demo-refresh-2', 'SHA256'))),
        FROM_TZ(SYS_EXTRACT_UTC(SYSTIMESTAMP), 'UTC') + INTERVAL '30' DAY);
COMMIT;

-- 6.4 Reutilizarea unei chei revocate (semn că a fost furată): backend-ul o caută după rezumat,
--     vede că este revocată și revocă toată familia, deci și cheia activă a atacatorului
DECLARE
  v_family  refresh_token.family_id%TYPE;
  v_revoked refresh_token.revoked%TYPE;
BEGIN
  SELECT family_id, revoked INTO v_family, v_revoked
    FROM refresh_token
   WHERE token_hash = LOWER(RAWTOHEX(STANDARD_HASH('demo-refresh-1', 'SHA256')));
  IF v_revoked THEN
    UPDATE refresh_token SET revoked = TRUE WHERE family_id = v_family AND revoked = FALSE;
    DBMS_OUTPUT.PUT_LINE('6.4 cheie reutilizată: familia a fost revocată (' || SQL%ROWCOUNT
                         || ' cheie activă revocată).');
  END IF;
  COMMIT;
END;
/

SELECT COUNT(*) AS chei_active_in_familie
  FROM refresh_token WHERE family_id = '&demo_family' AND revoked = FALSE;

-- 6.5 SAVEPOINT și ROLLBACK TO: se anulează doar partea de după punctul de salvare
UPDATE daily_log SET notes = 'Notă înainte de punctul de salvare.' WHERE user_id = '&demo_user';
SAVEPOINT dupa_nota;
UPDATE daily_log SET notes = 'Notă care va fi anulată.' WHERE user_id = '&demo_user';
INSERT INTO refresh_token (token_id, family_id, token_hash, expires_at, revoked)
VALUES ('&demo_token_3', '&demo_family', LOWER(RAWTOHEX(STANDARD_HASH('demo-refresh-3', 'SHA256'))),
        FROM_TZ(SYS_EXTRACT_UTC(SYSTIMESTAMP), 'UTC') + INTERVAL '30' DAY, TRUE);
ROLLBACK TO SAVEPOINT dupa_nota;
COMMIT;

SELECT notes,
       (SELECT COUNT(*) FROM refresh_token WHERE token_id = '&demo_token_3') AS jeton_anulat
  FROM daily_log WHERE user_id = '&demo_user';

-- 6.6 Exportul datelor utilizatorului (JSON) și câteva valori citite din el cu JSON_VALUE
SELECT JSON_VALUE(doc, '$.user.email') AS email,
       JSON_VALUE(doc, '$.analyses.size()') AS analize,
       JSON_VALUE(doc, '$.analyses[0].photos.size()') AS fotografii_analiza,
       JSON_VALUE(doc, '$.routines[0].steps.size()') AS pasi_rutina,
       JSON_VALUE(doc, '$.daily_logs[0].progress_photo') AS fotografie_progres,
       DBMS_LOB.GETLENGTH(doc) AS caractere
  FROM (SELECT export_user_json('&demo_user') AS doc FROM dual);

-- 6.7 O ștergere simplă a contului lasă fotografiile fără subclasă (PHOTO nu are cheie străină
--     spre utilizator), iar aserțiunea refuză COMMIT-ul: contul se șterge doar prin erase_user
BEGIN
  DELETE FROM app_user WHERE user_id = '&demo_user';
  COMMIT;
  RAISE_APPLICATION_ERROR(-20000, 'Eroare: COMMIT trebuia refuzat');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE IN (-2091, -8601) THEN DBMS_OUTPUT.PUT_LINE('6.7 așteptat: ' || SQLERRM); ELSE RAISE; END IF;
END;
/

-- =====================================================================================
-- 7. Utilizatorul aplicației (SKINCARE_APP): nu poate insera direct în PHOTO, dar poate folosi
--    photo_api; la sfârșit șterge contul de test prin erase_user, ca backend-ul
-- =====================================================================================
CONNECT skincare_app/"&1"@&2
SET SERVEROUTPUT ON

-- 7.1 INSERT direct în PHOTO: refuzat (ORA-41900 în 26ai). Instrucțiunea este dinamică (EXECUTE IMMEDIATE),
--     pentru că un INSERT static fără drept ar fi refuzat deja la compilarea blocului
BEGIN
  EXECUTE IMMEDIATE q'[INSERT INTO photo (photo_id, object_key, content_type, photo_kind)
                       VALUES ('0d000000-0000-4000-8000-0000000000f3',
                               'photos/0d000000-0000-4000-8000-0000000000f3', 'image/jpeg', 'ANALYSIS')]';
  RAISE_APPLICATION_ERROR(-20000, 'Eroare: SKINCARE_APP a putut insera în PHOTO');
EXCEPTION
  WHEN OTHERS THEN
    -- 26ai numește dreptul lipsă (ORA-41900); versiunile mai vechi dau ORA-01031
    IF SQLCODE IN (-41900, -1031) THEN DBMS_OUTPUT.PUT_LINE('7.1 așteptat: ' || SQLERRM); ELSE RAISE; END IF;
END;
/

DECLARE
  v_photo photo.photo_id%TYPE;
  v_log   daily_log.log_id%TYPE;
BEGIN
  -- o zi nouă în jurnal și fotografia ei, prin pachet
  INSERT INTO daily_log (user_id, log_date) VALUES ('&demo_user', DATE '2026-11-21')
  RETURNING log_id INTO v_log;
  v_photo := photo_api.add_progress_photo(v_log, 'Adăugată de aplicație');
  COMMIT;
  DBMS_OUTPUT.PUT_LINE('7.2 SKINCARE_APP a adăugat o fotografie prin photo_api.');
END;
/

-- 7.3 Ștergerea contului (GDPR art. 17): întâi fotografiile, apoi contul, cu toate rândurile lui
DECLARE
  v_photos PLS_INTEGER;
BEGIN
  v_photos := erase_user('&demo_user');
  COMMIT;
  DBMS_OUTPUT.PUT_LINE('7.3 cont șters prin erase_user; fotografii șterse: ' || v_photos);
END;
/

-- =====================================================================================
-- 8. Verificare: niciun rând al utilizatorului de test nu a rămas, iar datele comune au
--    din nou numărul de rânduri din seed.sql (7 utilizatori, 14 fotografii)
-- =====================================================================================
SELECT (SELECT COUNT(*) FROM app_user WHERE user_id = '&demo_user')
     + (SELECT COUNT(*) FROM consent WHERE user_id = '&demo_user')
     + (SELECT COUNT(*) FROM reminder WHERE user_id = '&demo_user')
     + (SELECT COUNT(*) FROM one_time_token WHERE user_id = '&demo_user')
     + (SELECT COUNT(*) FROM token_family WHERE user_id = '&demo_user')
     + (SELECT COUNT(*) FROM refresh_token WHERE family_id = '&demo_family')
     + (SELECT COUNT(*) FROM skin_analysis WHERE user_id = '&demo_user')
     + (SELECT COUNT(*) FROM prediction WHERE analysis_id = '&demo_analysis')
     + (SELECT COUNT(*) FROM answer WHERE analysis_id = '&demo_analysis')
     + (SELECT COUNT(*) FROM analysis_photo WHERE analysis_id = '&demo_analysis')
     + (SELECT COUNT(*) FROM routine WHERE user_id = '&demo_user')
     + (SELECT COUNT(*) FROM routine_step WHERE routine_id = '&demo_routine')
     + (SELECT COUNT(*) FROM daily_log WHERE user_id = '&demo_user') AS randuri_ramase,
       (SELECT COUNT(*) FROM app_user) AS utilizatori,
       (SELECT COUNT(*) FROM photo) AS fotografii;

PROMPT Script DML terminat.
DISCONNECT
EXIT SUCCESS
