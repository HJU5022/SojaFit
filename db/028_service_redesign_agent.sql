-- 서비스 표 재설계 2/3: 분석 서비스(sojafit_agent) 정리 — 화면 대화 FK · 체크포인트 삭제 트리거 · 회로 사본/죽은 승인 표 제거 · 청소 함수 교체.
-- 운영 이전용 migrate_prod_1_expand.sql(E2 · E5) + migrate_prod_3_contract_p2.sql을 빈 DB 한 번에 이어 붙인 것이다.
-- [주의] 이 파일은 013~017 · 022 · 023(sojafit_agent 표 · 함수)과 027 뒤에 돌아야 한다. initdb(파일 이름순)는 그렇게 돈다.
--        LangGraph 표(checkpoints 등)는 thread-setup이 initdb 뒤에 만들므로 트리거는 표가 있을 때만 지운다(to_regclass).
-- [주의] 앱 시작 코드가 013 · 022 · 023을 다시 적용하면 지운 표 · 바뀐 함수가 되살아난다. memory_service.initialize는 SQL 파일을 적용하지 않고 LangGraph 표만 만들어야 한다.
-- E2. 분석 대화와 화면 대화를 진짜 FK로 잇는다(같은 UUID, 대화를 지우면 분석 기록도 지워짐)
ALTER TABLE sojafit_agent.threads ADD CONSTRAINT fk_agent_threads_thread FOREIGN KEY (id) REFERENCES public.threads(id) ON DELETE CASCADE;
-- E5. 삭제 정합성: 대화 행이 지워질 때 체크포인트(LangGraph, FK 불가)를 DB가 같이 지운다. 옛 코드도 직접 지우므로 겹쳐도 무해하다
CREATE FUNCTION sojafit_agent.purge_thread_checkpoints() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    -- LangGraph 체크포인트 표 3개는 thread_id가 글자(text)라 FK를 걸 수 없다. 대화 행이 어떤 경로로 지워져도(프로젝트 · 계정 삭제의 cascade,
    -- 보관 기간 청소, 운영자의 직접 삭제) 질문 · 답이 든 체크포인트가 고아로 남지 않게 DB가 직접 지운다. 표는 `memory_service --setup` 뒤에 생기므로 있을 때만.
    IF to_regclass('sojafit_agent.checkpoints') IS NOT NULL THEN
        DELETE FROM sojafit_agent.checkpoint_writes WHERE thread_id = OLD.id::text;
        DELETE FROM sojafit_agent.checkpoint_blobs WHERE thread_id = OLD.id::text;
        DELETE FROM sojafit_agent.checkpoints WHERE thread_id = OLD.id::text;
    END IF;
    RETURN OLD;
END $$;
CREATE TRIGGER trg_threads_purge_checkpoints BEFORE DELETE ON public.threads
    FOR EACH ROW EXECUTE FUNCTION sojafit_agent.purge_thread_checkpoints();
REVOKE ALL ON FUNCTION sojafit_agent.purge_thread_checkpoints() FROM PUBLIC;


-- C3. 분석 서비스: 회로 사본 · 죽은 승인 표 제거, 삭제 규칙을 CASCADE로
ALTER TABLE sojafit_agent.threads DROP CONSTRAINT threads_circuit_id_fkey;
ALTER TABLE sojafit_agent.threads DROP COLUMN circuit_id;
ALTER TABLE sojafit_agent.threads DROP CONSTRAINT threads_user_id_fkey;
ALTER TABLE sojafit_agent.threads ADD CONSTRAINT threads_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
DROP TABLE sojafit_agent.circuits;
DROP TABLE sojafit_agent.approvals;

-- C5. 청소 함수 교체(같은 이름 · 같은 인자). 새 본문은 baseline_service.sql과 같다
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


INSERT INTO public.app_migrations (version, note) VALUES ('2026-11-contract-p2', 'db/028: 분석 회로 사본 · 죽은 승인 표 제거, 삭제 규칙 CASCADE, 체크포인트 삭제 트리거, 청소 함수 교체');
