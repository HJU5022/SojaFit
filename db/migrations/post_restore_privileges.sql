-- 백업 복원 직후 권한 복구 + 점검. **db/026 재실행 뒤**에 돌린다(026이 표 RLS와 공개 역할 표 권한을 다시 맞춘다).
-- 사용: psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/026_revoke_public_grants_and_rls.sql -f db/migrations/post_restore_privileges.sql
-- [왜] pg_restore --no-privileges는 함수의 EXECUTE 권한 정보(REVOKE ... FROM PUBLIC)를 복원하지 않아, 복원한 함수(sojafit_agent.purge_inactive_projects ·
--      purge_log_records · purge_thread_checkpoints, public.quote_snapshot_has_forbidden_key 등)가 기본값대로 PUBLIC 실행 가능이 된다. 026은 그중 public의 두 함수만 다시 막는다.
-- 하는 일: 복원 전 상태를 NOTICE로 찍고 → 두 스키마의 우리 함수 전부에서 PUBLIC(과 anon · authenticated가 있으면 그 역할) EXECUTE를 회수 → 아래를 확인해 하나라도 어긋나면 EXCEPTION:
--   PUBLIC 실행 가능 함수 0개, PUBLIC · 공개 역할 표 권한 0개, RLS가 꺼진 표 0개(확장 · LangGraph 표 제외).
DO $$
DECLARE
    item record;
    role_name text;
    n bigint;
BEGIN
    SELECT count(*) INTO n FROM pg_proc p JOIN pg_namespace ns ON ns.oid = p.pronamespace, LATERAL aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner))) a
        WHERE ns.nspname IN ('public', 'sojafit_agent') AND a.grantee = 0 AND a.privilege_type = 'EXECUTE'
          AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e');
    RAISE NOTICE '[복원 직후] PUBLIC 실행 가능 함수: %', n;
    FOR item IN
        SELECT p.oid::regprocedure AS signature FROM pg_proc p JOIN pg_namespace ns ON ns.oid = p.pronamespace
        WHERE ns.nspname IN ('public', 'sojafit_agent') AND pg_get_userbyid(p.proowner) = current_user
          AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e')
    LOOP
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', item.signature);
        FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated'] LOOP
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
                EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %I', item.signature, role_name);
            END IF;
        END LOOP;
    END LOOP;

    SELECT count(*) INTO n FROM pg_proc p JOIN pg_namespace ns ON ns.oid = p.pronamespace, LATERAL aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner))) a
        WHERE ns.nspname IN ('public', 'sojafit_agent') AND a.privilege_type = 'EXECUTE'
          AND (a.grantee = 0 OR pg_get_userbyid(a.grantee) IN ('anon', 'authenticated'))
          AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e');
    IF n > 0 THEN RAISE EXCEPTION '공개 역할이 실행할 수 있는 함수가 % 개 남았다', n; END IF;

    SELECT count(*) INTO n FROM pg_class c JOIN pg_namespace ns ON ns.oid = c.relnamespace, LATERAL aclexplode(c.relacl) a
        WHERE ns.nspname IN ('public', 'sojafit_agent') AND c.relkind IN ('r', 'p', 'S') AND (a.grantee = 0 OR pg_get_userbyid(a.grantee) IN ('anon', 'authenticated'));
    IF n > 0 THEN RAISE EXCEPTION 'PUBLIC · 공개 역할 권한이 남은 표 · 시퀀스가 % 개다(026을 먼저 다시 실행하라)', n; END IF;

    SELECT count(*) INTO n FROM pg_class c JOIN pg_namespace ns ON ns.oid = c.relnamespace
        WHERE ns.nspname IN ('public', 'sojafit_agent') AND c.relkind IN ('r', 'p') AND NOT c.relrowsecurity AND pg_get_userbyid(c.relowner) = current_user
          AND c.relname !~ '^(checkpoint|store|vector_migrations)'
          AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype = 'e');
    IF n > 0 THEN RAISE EXCEPTION 'RLS가 꺼진 표가 % 개다(026을 먼저 다시 실행하라)', n; END IF;
    RAISE NOTICE '[복원 뒤 점검 통과] PUBLIC 실행 함수 0 · 공개 권한 표 0 · RLS OFF 표 0';
END $$;
