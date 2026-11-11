-- 공개 역할(anon · authenticated)의 권한을 모두 회수하고 앱 표의 RLS를 켠다(11-10 운영 DB 점검, 여러 번 돌려도 같음).
--
-- [왜] 서버는 DB 소유자 연결(DATABASE_URL, 운영은 postgres)로만 접속하고 Supabase Data API · 공개 역할을 쓰지 않는다. 그런데 운영 DB에는
--      ① 코퍼스 표 4개(source_documents · document_chunks · chunk_embeddings · chunk_embedding_bits)에 anon · authenticated가 읽기 · 쓰기 · 삭제 ·
--      TRUNCATE 권한을 그대로 갖고 있었고 ② 그 표의 시퀀스 2개에도 권한이 있었고 ③ public에 앞으로 만드는 표 · 시퀀스 · 함수가 자동으로 같은 권한을 받는
--      기본 권한(Supabase 기본값)이 있었고 ④ sojafit_agent 표는 RLS가 꺼져 있었다. RLS(정책 없음 = 기본 거부)만으로 지금은 공개 역할이 0행이지만
--      방어가 한 겹뿐이었다. 권한까지 회수하고 RLS를 모든 앱 표에 켜 두 겹으로 만든다.
-- [영향] 표 소유자(운영 postgres · compose app)와 슈퍼유저는 RLS를 우회하므로 서버 동작은 그대로다. 소유자가 아닌 일반 역할이 소유 표를 쓰는 곳은 없다.
--        LangGraph 체크포인트 · Store 표도 BYPASSRLS 없는 일반 소유자 역할로 RLS ON 뒤 setup · put · get이 되는 것을 확인했다(tests/api/test_public_grants.py).
-- [안 하는 일] 표 · 데이터 삭제, 스키마 USAGE 회수(Supabase 기본값 유지), service_role 변경(프로젝트 관리자 키 역할), Supabase가 만든 함수(rls_auto_enable) 변경,
--              FORCE ROW LEVEL SECURITY(소유자까지 막으면 서버가 깨진다).
-- anon · authenticated 역할이 없는 DB(일반 Postgres · compose · CI)에서는 회수 부분을 건너뛰고 RLS만 켠다.
--
-- 적용 뒤 확인(둘 다 0행이어야 한다):
--   SELECT n.nspname, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace, LATERAL aclexplode(c.relacl) a
--    WHERE n.nspname IN ('public', 'sojafit_agent') AND c.relkind IN ('r', 'p', 'S') AND (a.grantee = 0 OR pg_get_userbyid(a.grantee) IN ('anon', 'authenticated'));
--   SELECT n.nspname, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
--    WHERE n.nspname IN ('public', 'sojafit_agent') AND c.relkind IN ('r', 'p') AND NOT c.relrowsecurity AND pg_get_userbyid(c.relowner) = current_user;
-- 되돌리기(권한만, RLS는 정책이 없어 영향 없음): 코퍼스 표 4개에 GRANT ALL ... TO anon, authenticated; (운영에서는 되돌릴 이유가 없다)
DO $$
DECLARE
    role_name text;
    item record;
BEGIN
    -- 1. 앱 표 전부 RLS ON. 내 소유가 아닌 표(확장 · 플랫폼이 만든 것)는 건드리지 않는다
    FOR item IN
        SELECT n.nspname, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN ('public', 'sojafit_agent') AND c.relkind IN ('r', 'p') AND pg_get_userbyid(c.relowner) = current_user
    LOOP
        EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY', item.nspname, item.relname);
    END LOOP;

    -- 2. 우리가 만든 함수 2개(CHECK 제약이 부름)는 공개 역할이 RPC로 부를 이유가 없다. 소유자는 그대로 실행한다
    FOR item IN
        SELECT p.oid::regprocedure AS signature FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname IN ('conversation_json_matches', 'quote_snapshot_has_forbidden_key')
          AND pg_get_userbyid(p.proowner) = current_user
    LOOP
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', item.signature);
    END LOOP;

    -- 3. 공개 역할 권한 회수(없는 역할은 건너뜀)
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            CONTINUE;
        END IF;
        EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', role_name);
        EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', role_name);
        IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'sojafit_agent') THEN
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA sojafit_agent FROM %I', role_name);
            EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA sojafit_agent FROM %I', role_name);
        END IF;
        FOR item IN
            SELECT p.oid::regprocedure AS signature FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND p.proname IN ('conversation_json_matches', 'quote_snapshot_has_forbidden_key')
              AND pg_get_userbyid(p.proowner) = current_user
        LOOP
            EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %I', item.signature, role_name);
        END LOOP;
        -- 앞으로 이 연결 역할이 public에 만드는 표 · 시퀀스 · 함수가 공개 역할 권한을 자동으로 받지 않게 한다
        EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I', role_name);
        EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I', role_name);
        EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM %I', role_name);
    END LOOP;
END $$;
