-- =====================================================================================
-- Vederi și interogări numerotate (Task O7)
-- Oracle AI Database 26ai Free, utilizatorul SKINCARE. Rulare după seed.sql (și, opțional,
-- dml.sql, care lasă datele comune neschimbate):
--   sql skincare@//localhost:1521/FREEPDB1 @db/oracle/queries.sql
--
-- Fiecare interogare are un număr, numărul de rânduri așteptat pe datele din seed.sql și
-- enunțul. Data de referință a datelor de test este 01.11.2026 (reference_time din
-- db/seed/seed_data.yaml); interogările o folosesc în locul datei curente, ca rezultatele să nu
-- se schimbe în timp.
--
-- Secțiuni: 1 vederi pentru atributele derivate | 2 selecție și proiecție | 3 joncțiuni |
--           4 operatori pe mulțimi | 5 subinterogări | 6 grupare | 7 interogări avansate |
--           8 vedere actualizabilă WITH CHECK OPTION și DROP VIEW
-- =====================================================================================

SET DEFINE OFF
SET SQLBLANKLINES ON
SET SERVEROUTPUT ON
SET LINESIZE 200
SET PAGESIZE 100
SET FEEDBACK ON
WHENEVER SQLERROR EXIT FAILURE ROLLBACK

-- =====================================================================================
-- 1. Vederi pentru atributele derivate, scoase din tabele la normalizare (o valoare care se
--    poate calcula din altele nu se păstrează, ca să nu poată deveni contradictorie)
-- =====================================================================================

-- 1.1 Rezultatul unei analize: încrederea generală = cea mai mare probabilitate; categoria
--     principală se arată doar când statusul este answered. KEEP (DENSE_RANK FIRST ...) ia
--     categoria de pe primul rând în ordinea probabilităților
CREATE OR REPLACE VIEW v_analysis_result AS
SELECT a.analysis_id, a.user_id, a.created_at, a.status,
       MAX(p.probability) AS overall_confidence,
       CASE WHEN a.status = 'answered'
            THEN MAX(p.concern_code) KEEP (DENSE_RANK FIRST ORDER BY p.probability DESC, p.concern_code)
       END AS top_concern
  FROM skin_analysis a
  JOIN prediction p ON p.analysis_id = a.analysis_id
 GROUP BY a.analysis_id, a.user_id, a.created_at, a.status;

-- 1.2 Locul fiecărei categorii într-o analiză (funcție fereastră: numerotare în cadrul analizei,
--     egalitățile se departajează după cod)
CREATE OR REPLACE VIEW v_prediction_rank AS
SELECT p.analysis_id, p.concern_code, p.probability,
       ROW_NUMBER() OVER (PARTITION BY p.analysis_id ORDER BY p.probability DESC, p.concern_code) AS rank
  FROM prediction p;

-- 1.3 Profilul utilizatorului cu vârsta și grupa de vârstă calculate la data curentă
CREATE OR REPLACE VIEW v_user_profile AS
SELECT u.user_id, u.first_name, u.skin_type, u.main_concern, u.climate, u.language,
       TRUNC(MONTHS_BETWEEN(SYSDATE, u.date_of_birth) / 12) AS age,
       CASE
         WHEN MONTHS_BETWEEN(SYSDATE, u.date_of_birth) < 20 * 12 THEN '18-19'
         WHEN MONTHS_BETWEEN(SYSDATE, u.date_of_birth) < 30 * 12 THEN '20-29'
         WHEN MONTHS_BETWEEN(SYSDATE, u.date_of_birth) < 40 * 12 THEN '30-39'
         WHEN MONTHS_BETWEEN(SYSDATE, u.date_of_birth) < 50 * 12 THEN '40-49'
         WHEN MONTHS_BETWEEN(SYSDATE, u.date_of_birth) < 60 * 12 THEN '50-59'
         ELSE '60+'
       END AS age_range
  FROM app_user u;

-- 1.4 Scorul de siguranță al unui produs: media scorurilor ingredientelor ponderată cu
--     1/poziție (primele ingrediente de pe listă au concentrația cea mai mare), rotunjită;
--     numărul de ingrediente din fiecare bandă și marcajele distincte. LEFT JOIN păstrează și
--     produsele fără listă de ingrediente (scor NULL)
CREATE OR REPLACE VIEW v_product_safety AS
SELECT p.product_id, p.name, p.brand, p.category,
       ROUND(SUM(i.score / pi.position) / SUM(1 / pi.position)) AS safety_score,
       COUNT(pi.ingredient_id) AS ingredients,
       COUNT(CASE WHEN i.score >= 70 THEN 1 END) AS safe_count,
       COUNT(CASE WHEN i.score BETWEEN 40 AND 69 THEN 1 END) AS caution_count,
       COUNT(CASE WHEN i.score < 40 THEN 1 END) AS irritant_count,
       (SELECT LISTAGG(DISTINCT f.flag, ', ') WITHIN GROUP (ORDER BY f.flag)
          FROM product_ingredient x
          JOIN ingredient_flag f ON f.ingredient_id = x.ingredient_id
         WHERE x.product_id = p.product_id) AS flags
  FROM product p
  LEFT JOIN product_ingredient pi ON pi.product_id = p.product_id
  LEFT JOIN ingredient i ON i.ingredient_id = pi.ingredient_id
 GROUP BY p.product_id, p.name, p.brand, p.category;

-- aplicația citește vederile (numele se rezolvă în schema SKINCARE)
GRANT SELECT ON v_analysis_result TO skincare_app;
GRANT SELECT ON v_prediction_rank TO skincare_app;
GRANT SELECT ON v_user_profile TO skincare_app;
GRANT SELECT ON v_product_safety TO skincare_app;

-- =====================================================================================
-- 2. Selecție, proiecție, expresii
-- =====================================================================================

-- Q01 (rânduri așteptate: 14) Să se afișeze mărcile distincte ale produselor, în ordine alfabetică.
SELECT DISTINCT brand AS marca
  FROM product
 ORDER BY brand;

-- Q02 (rânduri așteptate: 6) Să se afișeze produsele al căror nume conține „micell”, fără să conteze majusculele, cu mărimea ambalajului sau „necunoscută”.
SELECT p.name AS produs, p.brand AS marca, NVL(p.pack_size, 'necunoscută') AS ambalaj
  FROM product p
 WHERE LOWER(p.name) LIKE '%micell%'
 ORDER BY p.brand, p.name;

-- Q03 (rânduri așteptate: 4) Să se afișeze analizele cu scorul de fotografie neobișnuită între 0,30 și 0,40 și statusul answered sau uncertain, de la cel mai mare scor.
SELECT analysis_id, status, ood_score
  FROM skin_analysis
 WHERE ood_score BETWEEN 0.30 AND 0.40
   AND status IN ('answered', 'uncertain')
 ORDER BY ood_score DESC;

-- Q04 (rânduri așteptate: 1) Să se afișeze utilizatorii care nu și-au verificat încă adresa de e-mail.
SELECT email, created_at
  FROM app_user
 WHERE email_verified_at IS NULL
 ORDER BY created_at;

-- Q05 (rânduri așteptate: 7) Să se afișeze, pentru fiecare utilizator, vârsta în ani împliniți și numărul de zile de la înregistrare, la data de referință 01.11.2026, de la cel mai în vârstă.
SELECT first_name AS prenume,
       TRUNC(MONTHS_BETWEEN(DATE '2026-11-01', date_of_birth) / 12) AS varsta,
       DATE '2026-11-01' - TRUNC(CAST(created_at AS DATE)) AS zile_de_la_inregistrare
  FROM app_user
 ORDER BY varsta DESC, prenume;

-- =====================================================================================
-- 3. Joncțiuni (combinarea rândurilor din mai multe tabele)
-- =====================================================================================

-- Q06 (rânduri așteptate: 8) Să se afișeze adresa de e-mail și data fiecărei analize, cu joncțiunea scrisă în clauza WHERE.
SELECT u.email, a.created_at, a.status
  FROM app_user u, skin_analysis a
 WHERE u.user_id = a.user_id
 ORDER BY u.email, a.created_at;

-- Q07 (rânduri așteptate: 7) Să se afișeze răspunsurile din prima analiză a utilizatoarei ana.popescu@example.com, cu textul întrebării și eticheta variantei (INNER JOIN pe patru tabele).
SELECT q.question_id, q.text AS intrebare, o.label AS raspuns
  FROM skin_analysis a
  INNER JOIN app_user u ON u.user_id = a.user_id
  INNER JOIN answer an ON an.analysis_id = a.analysis_id
  INNER JOIN question_option o ON o.question_id = an.question_id AND o.option_value = an.option_value
  INNER JOIN question q ON q.question_id = an.question_id
 WHERE u.email = 'ana.popescu@example.com'
   AND a.created_at = (SELECT MIN(created_at) FROM skin_analysis WHERE user_id = u.user_id)
 ORDER BY q.question_id, o.position;

-- Q08 (rânduri așteptate: 65) Să se afișeze perechile de produse care au cel puțin trei ingrediente comune (auto-joncțiune pe PRODUCT_INGREDIENT).
SELECT p1.name AS produs_1, p2.name AS produs_2, COUNT(*) AS ingrediente_comune
  FROM product_ingredient a
  JOIN product_ingredient b ON b.ingredient_id = a.ingredient_id AND b.product_id > a.product_id
  JOIN product p1 ON p1.product_id = a.product_id
  JOIN product p2 ON p2.product_id = b.product_id
 GROUP BY p1.name, p2.name
HAVING COUNT(*) >= 3
 ORDER BY ingrediente_comune DESC, produs_1, produs_2;

-- Q09 (rânduri așteptate: 4) Să se afișeze probabilitățile primei analize a utilizatoarei ana.popescu@example.com, cu numele categoriei (NATURAL JOIN pe coloana comună concern_code).
SELECT name AS categorie, probability
  FROM prediction NATURAL JOIN skin_concern
 WHERE analysis_id = (SELECT a.analysis_id
                        FROM skin_analysis a JOIN app_user u ON u.user_id = a.user_id
                       WHERE u.email = 'ana.popescu@example.com'
                       ORDER BY a.created_at
                       FETCH FIRST 1 ROW ONLY)
 ORDER BY probability DESC;

-- Q10 (rânduri așteptate: 5) Să se afișeze variantele de răspuns care declanșează mesajul „consultați un medic”, cu întrebarea lor (JOIN ... USING).
SELECT question_id, field_key, option_value, label
  FROM question JOIN question_option USING (question_id)
 WHERE is_red_flag
 ORDER BY question_id, position;

-- Q11 (rânduri așteptate: 7) Să se afișeze toți utilizatorii cu numărul lor de analize, inclusiv cei fără nicio analiză (LEFT JOIN).
SELECT u.email, COUNT(a.analysis_id) AS analize
  FROM app_user u
  LEFT JOIN skin_analysis a ON a.user_id = u.user_id
 GROUP BY u.email
 ORDER BY analize DESC, u.email;

-- Q12 (rânduri așteptate: 1) Să se afișeze ingredientele care nu apar în niciun produs (RIGHT JOIN).
SELECT i.inci_name, i.score
  FROM product_ingredient pi
 RIGHT JOIN ingredient i ON i.ingredient_id = pi.ingredient_id
 WHERE pi.product_id IS NULL
 ORDER BY i.inci_name;

-- Q13 (rânduri așteptate: 2) Să se afișeze perechile (utilizator, perioadă) care au memento dar nu au rutină sau au rutină dar nu au memento (FULL OUTER JOIN).
SELECT COALESCE(m.user_id, r.user_id) AS user_id, COALESCE(m.period, r.period) AS perioada,
       CASE WHEN m.user_id IS NULL THEN 'rutină fără memento' ELSE 'memento fără rutină' END AS situatie
  FROM reminder m
  FULL OUTER JOIN (SELECT DISTINCT user_id, period FROM routine) r
    ON r.user_id = m.user_id AND r.period = m.period
 WHERE m.user_id IS NULL OR r.user_id IS NULL
 ORDER BY user_id, perioada;

-- =====================================================================================
-- 4. Operatori pe mulțimi
-- =====================================================================================

-- Q14 (rânduri așteptate: 5) Să se afișeze utilizatorii care au un memento sau o rutină (UNION elimină duplicatele).
SELECT user_id FROM reminder
UNION
SELECT user_id FROM routine
 ORDER BY 1;

-- Q15 (rânduri așteptate: 4) Să se afișeze utilizatorii care au și analize, și înregistrări în jurnal (INTERSECT).
SELECT user_id FROM skin_analysis
INTERSECT
SELECT user_id FROM daily_log
 ORDER BY 1;

-- Q16 (rânduri așteptate: 2) Să se afișeze utilizatorii care nu au nicio analiză (MINUS).
SELECT user_id FROM app_user
MINUS
SELECT user_id FROM skin_analysis
 ORDER BY 1;

-- =====================================================================================
-- 5. Subinterogări
-- =====================================================================================

-- Q17 (rânduri așteptate: 9) Să se afișeze produsele care conțin cel puțin un ingredient marcat ca parfum (IN cu subinterogare).
SELECT name, brand
  FROM product
 WHERE product_id IN (SELECT pi.product_id
                        FROM product_ingredient pi
                        JOIN ingredient_flag f ON f.ingredient_id = pi.ingredient_id
                       WHERE f.flag = 'fragrance')
 ORDER BY brand, name;

-- Q18 (rânduri așteptate: 5) Să se afișeze cea mai recentă analiză a fiecărui utilizator (IN pe perechi de coloane).
SELECT user_id, analysis_id, created_at, status
  FROM skin_analysis
 WHERE (user_id, created_at) IN (SELECT user_id, MAX(created_at) FROM skin_analysis GROUP BY user_id)
 ORDER BY user_id;

-- Q19 (rânduri așteptate: 3) Să se afișeze produsul (sau produsele) cu cele mai multe ingrediente (subinterogare scalară cu =).
SELECT p.name, COUNT(*) AS ingrediente
  FROM product p JOIN product_ingredient pi ON pi.product_id = p.product_id
 GROUP BY p.product_id, p.name
HAVING COUNT(*) = (SELECT MAX(COUNT(*)) FROM product_ingredient GROUP BY product_id);

-- Q20 (rânduri așteptate: 4) Să se afișeze ingredientele fără niciun marcaj al căror scor nu depășește scorul măcar unui ingredient marcat (<= ANY); sunt candidatele pentru o revizuire a scorurilor.
SELECT i.inci_name, i.score
  FROM ingredient i
 WHERE NOT EXISTS (SELECT 1 FROM ingredient_flag f WHERE f.ingredient_id = i.ingredient_id)
   AND i.score <= ANY (SELECT x.score
                         FROM ingredient x JOIN ingredient_flag f ON f.ingredient_id = x.ingredient_id)
 ORDER BY i.score, i.inci_name;

-- Q21 (rânduri așteptate: 5) Să se afișeze ingredientele cu scorul cel mai mare (>= ALL).
SELECT inci_name, score
  FROM ingredient
 WHERE score >= ALL (SELECT score FROM ingredient)
 ORDER BY inci_name;

-- Q22 (rânduri așteptate: 12) Să se afișeze probabilitățile mai mari decât media probabilităților aceleiași categorii (subinterogare corelată).
SELECT p.analysis_id, p.concern_code, p.probability
  FROM prediction p
 WHERE p.probability > (SELECT AVG(x.probability) FROM prediction x WHERE x.concern_code = p.concern_code)
 ORDER BY p.concern_code, p.probability DESC;

-- Q23 (rânduri așteptate: 1) Să se afișeze utilizatorii care și-au retras cel puțin un consimțământ (EXISTS).
SELECT u.email
  FROM app_user u
 WHERE EXISTS (SELECT 1 FROM consent c WHERE c.user_id = u.user_id AND c.withdrawn_at IS NOT NULL);

-- Q24 (rânduri așteptate: 2) Să se afișeze utilizatorii fără nicio analiză în cele 30 de zile dinaintea datei de referință (NOT EXISTS).
SELECT u.email
  FROM app_user u
 WHERE NOT EXISTS (SELECT 1
                     FROM skin_analysis a
                    WHERE a.user_id = u.user_id
                      AND a.created_at >= TIMESTAMP '2026-11-01 00:00:00 +00:00' - INTERVAL '30' DAY)
 ORDER BY u.email;

-- =====================================================================================
-- 6. Funcții de grup, GROUP BY și HAVING
-- =====================================================================================

-- Q25 (rânduri așteptate: 3) Să se afișeze, pentru fiecare categorie, numărul de probabilități, media, minimul și maximul, doar pentru categoriile cu media peste 0,20.
SELECT concern_code, COUNT(*) AS numar, ROUND(AVG(probability), 4) AS media,
       MIN(probability) AS minim, MAX(probability) AS maxim, SUM(probability) AS suma
  FROM prediction
 GROUP BY concern_code
HAVING AVG(probability) > 0.20
 ORDER BY media DESC;

-- Q26 (rânduri așteptate: 3) Să se afișeze numărul de analize pentru fiecare lună și status.
SELECT TO_CHAR(created_at, 'YYYY-MM') AS luna, status, COUNT(*) AS analize
  FROM skin_analysis
 GROUP BY TO_CHAR(created_at, 'YYYY-MM'), status
 ORDER BY luna, status;

-- Q27 (rânduri așteptate: 1) Să se afișeze utilizatorii care au bifat în jurnal mai mult de trei produse diferite (COUNT(DISTINCT ...)).
SELECT l.user_id, COUNT(DISTINCT pu.product_id) AS produse_diferite, COUNT(*) AS bifari
  FROM daily_log l JOIN product_use pu ON pu.log_id = l.log_id
 GROUP BY l.user_id
HAVING COUNT(DISTINCT pu.product_id) > 3
 ORDER BY produse_diferite DESC;

-- Q28 (rânduri așteptate: 5) Să se afișeze aderența la rutină: procentul zilelor din jurnal în care utilizatorul a bifat produse în fiecare perioadă (AM, PM) pentru care are o rutină (subinterogare în FROM).
SELECT z.user_id, z.zile, z.zile_complete, ROUND(100 * z.zile_complete / z.zile, 1) AS aderenta_procent
  FROM (SELECT l.user_id,
               COUNT(*) AS zile,
               SUM(CASE WHEN (SELECT COUNT(DISTINCT pu.period) FROM product_use pu WHERE pu.log_id = l.log_id)
                             >= (SELECT COUNT(DISTINCT r.period) FROM routine r WHERE r.user_id = l.user_id)
                        THEN 1 ELSE 0 END) AS zile_complete
          FROM daily_log l
         WHERE EXISTS (SELECT 1 FROM routine r WHERE r.user_id = l.user_id)
         GROUP BY l.user_id) z
 ORDER BY aderenta_procent DESC, z.user_id;

-- Q29 (rânduri așteptate: 7) Să se afișeze fiecare utilizator cu numărul de zile din jurnal și numărul de consimțăminte active (subinterogări în SELECT).
SELECT u.email,
       (SELECT COUNT(*) FROM daily_log l WHERE l.user_id = u.user_id) AS zile_jurnal,
       (SELECT COUNT(*) FROM consent c WHERE c.user_id = u.user_id AND c.withdrawn_at IS NULL) AS consimtaminte_active
  FROM app_user u
 ORDER BY zile_jurnal DESC, u.email;

-- Q30 (rânduri așteptate: 3) Să se afișeze numărul de ingrediente din fiecare bandă de siguranță (CASE).
SELECT CASE WHEN score >= 70 THEN 'safe' WHEN score >= 40 THEN 'caution' ELSE 'irritant' END AS banda,
       COUNT(*) AS ingrediente
  FROM ingredient
 GROUP BY CASE WHEN score >= 70 THEN 'safe' WHEN score >= 40 THEN 'caution' ELSE 'irritant' END
 ORDER BY ingrediente DESC;

-- =====================================================================================
-- 7. Interogări avansate
-- =====================================================================================

-- Q31 (rânduri așteptate: 2) Să se afișeze utilizatorii care pe 20.10.2026 au bifat dimineața toate produsele rutinei lor curente de dimineață (diviziune relațională: nu există niciun produs al rutinei care să nu fi fost bifat).
SELECT u.email
  FROM app_user u
 WHERE EXISTS (SELECT 1 FROM routine r WHERE r.user_id = u.user_id AND r.period = 'AM')
   AND NOT EXISTS (
         SELECT s.product_id
           FROM routine_step s
          WHERE s.product_id IS NOT NULL
            AND s.routine_id = (SELECT r.routine_id FROM routine r
                                 WHERE r.user_id = u.user_id AND r.period = 'AM'
                                 ORDER BY r.created_at DESC FETCH FIRST 1 ROW ONLY)
         MINUS
         SELECT pu.product_id
           FROM daily_log l JOIN product_use pu ON pu.log_id = l.log_id
          WHERE l.user_id = u.user_id AND l.log_date = DATE '2026-10-20' AND pu.period = 'AM')
   AND EXISTS (SELECT 1 FROM daily_log l WHERE l.user_id = u.user_id AND l.log_date = DATE '2026-10-20')
 ORDER BY u.email;

-- Q32 (rânduri așteptate: 5) Să se afișeze ultima analiză a fiecărui utilizator cu categoria principală și încrederea generală (WITH, expresie de tabel comună, peste vederea v_analysis_result).
WITH ultima AS (
  SELECT r.*, ROW_NUMBER() OVER (PARTITION BY r.user_id ORDER BY r.created_at DESC) AS nr
    FROM v_analysis_result r
)
SELECT u.email, ultima.created_at, ultima.status, ultima.top_concern, ultima.overall_confidence
  FROM ultima JOIN app_user u ON u.user_id = ultima.user_id
 WHERE ultima.nr = 1
 ORDER BY u.email;

-- Q33 (rânduri așteptate: 5) Să se afișeze cea mai lungă serie de zile consecutive din jurnal pentru fiecare utilizator (funcție fereastră: zilele unei serii au aceeași diferență dată - număr de ordine).
SELECT user_id, MAX(zile) AS cea_mai_lunga_serie
  FROM (SELECT user_id, COUNT(*) AS zile
          FROM (SELECT user_id, log_date,
                       log_date - ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY log_date) AS grupa
                  FROM daily_log)
         GROUP BY user_id, grupa)
 GROUP BY user_id
 ORDER BY cea_mai_lunga_serie DESC, user_id;

-- Q34 (rânduri așteptate: 5) Să se afișeze primele 5 produse după scorul de siguranță, cu marcajele lor (FETCH FIRST peste vederea v_product_safety).
SELECT name, brand, safety_score, ingredients, safe_count, caution_count, irritant_count, flags
  FROM v_product_safety
 WHERE safety_score IS NOT NULL
 ORDER BY safety_score DESC, name
 FETCH FIRST 5 ROWS ONLY;

-- Q35 (rânduri așteptate: 2) Să se afișeze a doua categorie ca probabilitate în fiecare analiză cu statusul uncertain (interogare pe vederea v_prediction_rank).
SELECT pr.analysis_id, pr.concern_code, pr.probability
  FROM v_prediction_rank pr
  JOIN skin_analysis a ON a.analysis_id = pr.analysis_id
 WHERE pr.rank = 2 AND a.status = 'uncertain'
 ORDER BY pr.analysis_id;

-- Q36 (rânduri așteptate: 1) Să se afișeze familiile de jetoane în care toate cheile sunt revocate deși există mai multe chei (semn de cheie reutilizată sau de deconectare).
SELECT f.family_id, f.user_id, COUNT(t.token_id) AS chei
  FROM token_family f JOIN refresh_token t ON t.family_id = f.family_id
 GROUP BY f.family_id, f.user_id
HAVING COUNT(t.token_id) >= 2 AND COUNT(CASE WHEN t.revoked = FALSE THEN 1 END) = 0;

-- Q37 (rânduri așteptate: 5) Să se afișeze grupa de vârstă și tipul de ten al utilizatorilor, cu numărul lor (interogare pe vederea v_user_profile).
SELECT age_range, skin_type, COUNT(*) AS utilizatori
  FROM v_user_profile
 GROUP BY age_range, skin_type
 ORDER BY age_range, skin_type;

-- =====================================================================================
-- 8. Vedere actualizabilă WITH CHECK OPTION și DROP VIEW
-- =====================================================================================

-- Mementourile active. O vedere pe un singur tabel, fără grupare, se poate actualiza;
-- WITH CHECK OPTION refuză orice modificare după care rândul n-ar mai fi vizibil în vedere
CREATE OR REPLACE VIEW v_enabled_reminder AS
SELECT reminder_id, user_id, period, time_of_day, enabled
  FROM reminder
 WHERE enabled = TRUE
  WITH CHECK OPTION CONSTRAINT ck_v_enabled_reminder;

GRANT SELECT, UPDATE ON v_enabled_reminder TO skincare_app;

-- modificarea orei prin vedere reușește (rândul rămâne activ), dezactivarea prin vedere este
-- refuzată (ORA-01402); ambele se anulează la sfârșit
BEGIN
  UPDATE v_enabled_reminder SET time_of_day = '08:15' WHERE period = 'AM' AND time_of_day = '07:30';
  DBMS_OUTPUT.PUT_LINE('UPDATE prin vedere: ' || SQL%ROWCOUNT || ' rând modificat.');
  BEGIN
    UPDATE v_enabled_reminder SET enabled = FALSE WHERE period = 'PM';
    RAISE_APPLICATION_ERROR(-20000, 'Eroare: WITH CHECK OPTION trebuia să refuze');
  EXCEPTION
    WHEN OTHERS THEN
      IF SQLCODE = -1402 THEN DBMS_OUTPUT.PUT_LINE('Așteptat: ' || SQLERRM); ELSE RAISE; END IF;
  END;
  ROLLBACK;
END;
/

SELECT COUNT(*) AS mementouri_active FROM v_enabled_reminder;

-- o vedere de lucru, creată și ștearsă
CREATE OR REPLACE VIEW v_tmp_products_without_barcode AS
SELECT product_id, name FROM product WHERE barcode IS NULL;

SELECT COUNT(*) AS produse_fara_cod FROM v_tmp_products_without_barcode;

DROP VIEW v_tmp_products_without_barcode;

PROMPT Interogări terminate.
