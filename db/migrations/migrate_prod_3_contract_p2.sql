-- 운영 DB 이전 3단계 "contract P2"(축소 2): 분석 서비스 정리. **되돌릴 수 없는 삭제**가 들어 있다. 초안, 아직 어디에도 실행하지 않았다.
--
-- 전제(하나라도 아니면 실행하지 않는다):
--   ① migrate_prod_1_expand.sql과 2_contract_p1을 적용했다
--   ② **P2 새 코드가 배포돼 100%이고** 스모크 28단계 · 계정 삭제 · 프로젝트 삭제 점검이 통과했다. P2 새 코드 = backend/conversations/memory_service.py가
--      sojafit_agent.circuits(분석 회로 사본)와 sojafit_agent.approvals(옛 승인 경로)를 읽지도 쓰지도 않고 회로 · 파일 이름은 public.circuits · projects에서 읽는다.
--   ③ 실행 직전 백업을 받았다.
-- 되돌리기: migrate_prod_4_rollback.sql의 B2 절(회로 사본은 public에서 다시 만든다, 승인 표는 0행이었다).
-- 데이터 손실 가드: 지워지는 표에 데이터가 있으면 명시 확인 없이는 중단한다. 같은 psql 세션에서 먼저 SET 한다:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "SET app.ack_drop_agent_approvals='yes'" -c "SET app.ack_drop_agent_circuits='yes'" -f db/migrations/migrate_prod_3_contract_p2.sql
BEGIN;

-- G1. 사전 점검(삭제 전)
DO $$
DECLARE n bigint;
BEGIN
    SELECT count(*) INTO n FROM sojafit_agent.approvals;
    RAISE NOTICE '[점검] sojafit_agent.approvals 행: % (0행이어야 한다. 이 표는 삭제된다)', n;
    IF n > 0 AND COALESCE(current_setting('app.ack_drop_agent_approvals', true), '') <> 'yes' THEN
        RAISE EXCEPTION 'sojafit_agent.approvals에 %행이 있다. 옛 승인 경로의 기록이라 되살릴 수 없다. 지워도 되면 SET app.ack_drop_agent_approvals=''yes'' 를 같은 세션에서 먼저 실행하라', n;
    END IF;
    -- 분석 회로 사본은 public.circuits의 복사본이라 지워도 되살린다(되돌리기 B2). 단 thread가 가리키지 않는 사본 · 대응하는 public 회로가 없는 사본은 되살릴 수 없다
    SELECT count(*) INTO n FROM sojafit_agent.circuits c
        WHERE NOT EXISTS (SELECT 1 FROM sojafit_agent.threads t JOIN public.threads pt ON pt.id = t.id JOIN public.circuits pc ON pc.project_id = pt.project_id WHERE t.circuit_id = c.id);
    RAISE NOTICE '[점검] 대응하는 public 회로가 없어 되살릴 수 없는 sojafit_agent.circuits 행: %', n;
    IF n > 0 AND COALESCE(current_setting('app.ack_drop_agent_circuits', true), '') <> 'yes' THEN
        RAISE EXCEPTION 'sojafit_agent.circuits % 행은 public.circuits에서 되살릴 수 없다(thread가 없거나 화면 대화가 없음). 지워도 되면 SET app.ack_drop_agent_circuits=''yes'' 를 먼저 실행하라', n;
    END IF;
END $$;

-- C3. 분석 서비스: 회로 사본 · 죽은 승인 표 제거, 삭제 규칙을 CASCADE로
ALTER TABLE sojafit_agent.threads DROP CONSTRAINT threads_circuit_id_fkey;
ALTER TABLE sojafit_agent.threads DROP COLUMN circuit_id;
ALTER TABLE sojafit_agent.threads DROP CONSTRAINT threads_user_id_fkey;
ALTER TABLE sojafit_agent.threads ADD CONSTRAINT threads_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
DROP TABLE sojafit_agent.circuits;
DROP TABLE sojafit_agent.approvals;

-- C5. 청소 함수 교체(같은 이름 · 같은 인자). 새 본문은 db/020_service_baseline.sql과 같다
CREATE OR REPLACE FUNCTION sojafit_agent.purge_inactive_projects(keep_days integer DEFAULT 60, batch_size integer DEFAULT 20)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE
    cutoff timestamptz := CURRENT_TIMESTAMP - make_interval(days => keep_days);
    victim record;
    done integer := 0;
BEGIN
    IF keep_days < 1 OR batch_size < 1 THEN
        RAISE EXCEPTION 'keep_days and batch_size must be positive';
    END IF;
    IF NOT pg_try_advisory_xact_lock(736128) THEN
        RETURN 0;
    END IF;
    FOR victim IN
        SELECT p.id FROM public.projects p
        WHERE GREATEST(p.updated_at,
                (SELECT max(t.created_at) FROM public.threads t WHERE t.project_id = p.id),
                (SELECT max(r.updated_at) FROM public.runs r JOIN public.threads t ON t.id = r.thread_id WHERE t.project_id = p.id),
                (SELECT max(a.created_at) FROM public.approvals a JOIN public.messages m ON m.id = a.message_id
                    JOIN public.threads t ON t.id = m.thread_id WHERE t.project_id = p.id),
                (SELECT max(q.created_at) FROM public.quotes q JOIN public.approvals a ON a.id = q.approval_id
                    JOIN public.messages m ON m.id = a.message_id JOIN public.threads t ON t.id = m.thread_id WHERE t.project_id = p.id)
              ) < cutoff
        ORDER BY p.updated_at, p.id
        LIMIT batch_size
        FOR UPDATE OF p SKIP LOCKED
    LOOP
        DELETE FROM public.projects WHERE id = victim.id;  -- 체크포인트는 expand가 만든 트리거가 지운다
        done := done + 1;
    END LOOP;
    RETURN done;
END $$;

CREATE OR REPLACE FUNCTION sojafit_agent.purge_log_records(keep_days integer DEFAULT 30, batch_size integer DEFAULT 200)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE
    cutoff timestamptz := CURRENT_TIMESTAMP - make_interval(days => keep_days);
    cutoff_day date := (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - keep_days;
    done integer := 0;
    n integer;
BEGIN
    IF keep_days < 1 OR batch_size < 1 THEN
        RAISE EXCEPTION 'keep_days and batch_size must be positive';
    END IF;
    IF NOT pg_try_advisory_xact_lock(736129) THEN
        RETURN 0;
    END IF;
    DELETE FROM sojafit_agent.analysis_events WHERE ctid = ANY(ARRAY(
        SELECT ctid FROM sojafit_agent.analysis_events WHERE created_at < cutoff LIMIT batch_size));
    GET DIAGNOSTICS n = ROW_COUNT; done := done + n;
    DELETE FROM sojafit_agent.analysis_usage WHERE ctid = ANY(ARRAY(
        SELECT ctid FROM sojafit_agent.analysis_usage WHERE day < cutoff_day LIMIT batch_size));
    GET DIAGNOSTICS n = ROW_COUNT; done := done + n;
    DELETE FROM sojafit_agent.analysis_service_usage WHERE ctid = ANY(ARRAY(
        SELECT ctid FROM sojafit_agent.analysis_service_usage WHERE day < cutoff_day LIMIT batch_size));
    GET DIAGNOSTICS n = ROW_COUNT; done := done + n;
    DELETE FROM public.auth_signup_attempts WHERE ctid = ANY(ARRAY(
        SELECT ctid FROM public.auth_signup_attempts WHERE day < cutoff_day LIMIT batch_size));
    GET DIAGNOSTICS n = ROW_COUNT; done := done + n;
    DELETE FROM public.auth_login_attempts WHERE ctid = ANY(ARRAY(
        SELECT ctid FROM public.auth_login_attempts
        WHERE (locked_until IS NULL OR locked_until <= CURRENT_TIMESTAMP) AND (window_started_at IS NULL OR window_started_at < cutoff)
        LIMIT batch_size));
    GET DIAGNOSTICS n = ROW_COUNT; done := done + n;
    DELETE FROM public.auth_login_ip_attempts WHERE ctid = ANY(ARRAY(
        SELECT ctid FROM public.auth_login_ip_attempts
        WHERE (locked_until IS NULL OR locked_until <= CURRENT_TIMESTAMP) AND (window_started_at IS NULL OR window_started_at < cutoff)
        LIMIT batch_size));
    GET DIAGNOSTICS n = ROW_COUNT; done := done + n;
    DELETE FROM public.auth_sessions WHERE ctid = ANY(ARRAY(
        SELECT ctid FROM public.auth_sessions WHERE expires_at < CURRENT_TIMESTAMP - interval '1 day' LIMIT batch_size));
    GET DIAGNOSTICS n = ROW_COUNT; done := done + n;
    RETURN done;
END $$;

INSERT INTO public.app_migrations (version, note) VALUES ('2026-11-contract-p2', 'migrate_prod_3_contract_p2.sql: 분석 회로 사본 · 죽은 승인 표 제거, 삭제 규칙 CASCADE, 청소 함수 교체');
COMMIT;
