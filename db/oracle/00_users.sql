-- =====================================================================================
-- Utilizatorii bazei de date Oracle pentru implementarea relațională de referință
-- (Oracle AI Database 26ai Free, baza de date conectabilă FREEPDB1).
--
--   SKINCARE      proprietarul schemei: creează tabelele, domeniile, vederile și codul PL/SQL
--   SKINCARE_APP  utilizatorul aplicației (backend-ul): se poate conecta și primește, prin
--                 db/oracle/skincare.sql, doar drepturile pe obiectele schemei SKINCARE de care
--                 are nevoie (principiul privilegiului minim, ca utilizatorul readWrite din Atlas)
--
-- Rulare, conectat ca SYSTEM la FREEPDB1, cu trei parametri:
--   sql system@//localhost:1521/FREEPDB1 @db/oracle/00_users.sql <parola_skincare> <parola_app> //localhost:1521/FREEPDB1
-- Parolele nu sunt scrise în fișier. Atenție: scriptul șterge și recreează ambii utilizatori,
-- deci șterge schema SKINCARE cu toate datele ei.
-- =====================================================================================

WHENEVER SQLERROR EXIT FAILURE
SET VERIFY OFF
SET SERVEROUTPUT ON

-- 1. Ștergerea utilizatorilor existenți (IF EXISTS: scriptul poate fi rulat de mai multe ori)
DROP USER IF EXISTS skincare_app CASCADE;
DROP USER IF EXISTS skincare CASCADE;

-- 2. Proprietarul schemei: spațiu nelimitat în tablespace-ul USERS și doar drepturile de
--    creare a obiectelor folosite de scripturi (fără rolul DBA)
CREATE USER skincare IDENTIFIED BY "&1"
  DEFAULT TABLESPACE users
  QUOTA UNLIMITED ON users;

GRANT CREATE SESSION, CREATE TABLE, CREATE VIEW, CREATE SEQUENCE, CREATE PROCEDURE,
      CREATE TRIGGER, CREATE DOMAIN
   TO skincare;

-- 3. Utilizatorul aplicației: se poate doar conecta; nu are spațiu de stocare și nu poate crea
--    obiecte. Drepturile pe tabele le acordă proprietarul, în secțiunea 6 din skincare.sql
CREATE USER skincare_app IDENTIFIED BY "&2";

GRANT CREATE SESSION TO skincare_app;

-- 4. La conectarea lui SKINCARE_APP, numele de obiecte se rezolvă în schema SKINCARE,
--    deci aplicația scrie app_user, nu skincare.app_user (fără sinonime pentru fiecare obiect)
CREATE OR REPLACE TRIGGER skincare_app_logon
  AFTER LOGON ON skincare_app.SCHEMA
BEGIN
  EXECUTE IMMEDIATE 'ALTER SESSION SET CURRENT_SCHEMA = SKINCARE';
END;
/

-- 5. Verificare: ambii utilizatori se pot conecta, iar SKINCARE_APP nu poate crea tabele
CONNECT skincare/"&1"@&3
SELECT USER AS utilizator, COUNT(*) AS drepturi_sistem FROM session_privs;

CONNECT skincare_app/"&2"@&3
SELECT USER AS utilizator, SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') AS schema_curenta;

BEGIN
  EXECUTE IMMEDIATE 'CREATE TABLE t_privilege_test (x NUMBER)';
  RAISE_APPLICATION_ERROR(-20000, 'Eroare: SKINCARE_APP a putut crea un tabel');
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -1031 THEN
      DBMS_OUTPUT.PUT_LINE('OK: SKINCARE_APP nu are dreptul CREATE TABLE (ORA-01031).');
    ELSE
      RAISE;
    END IF;
END;
/

DISCONNECT
EXIT SUCCESS
