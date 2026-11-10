-- 보관 기간 청소 함수 2개(11-09 결정, SPEC 8.5). 규칙 하나 = 함수 하나이고, 앱이 새 분석을 시작할 때 작은 묶음으로 부른다(스케줄러 없음,
-- backend/conversations/memory_service.py `Conversations._purge_expired`).
-- [왜] 60일: 회로는 몇 주 뒤에 다시 여는 일이 많아 한 달보다 넉넉히 둔다. 30일: 기록은 최근 디버깅과 남용 한도 확인에만 쓴다.
-- Supabase pg_cron으로 하루 한 번 같은 함수를 부를 수 있다(지금은 켜지 않음). 예:
--   SELECT cron.schedule('sojafit-retention', '0 18 * * *', 'SELECT sojafit_agent.purge_inactive_projects(); SELECT sojafit_agent.purge_log_records();');
-- 함수는 공개 역할이 쓸 수 없는 sojafit_agent 스키마에 두고 EXECUTE 권한도 회수한다(Supabase API로 부를 수 없게).
-- 새 볼륨은 이름순으로 자동 실행되고(018~022 다음), 분석 준비 명령(memory_service --setup)이 다시 실행해도 같은 함수로 바뀔 뿐이다.

-- 프로젝트 · 분석 대화: 마지막 활동 뒤 keep_days일이 지나면 딸린 것까지 지운다. 지운 묶음 수(프로젝트 + 분석 thread + 빈 회로)를 돌려준다.
CREATE OR REPLACE FUNCTION sojafit_agent.purge_inactive_projects(keep_days integer DEFAULT 60, batch_size integer DEFAULT 20)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE
    cutoff timestamptz := CURRENT_TIMESTAMP - make_interval(days => keep_days);
    victim record;
    ids uuid[];
    done integer := 0;
    n integer;
BEGIN
    IF keep_days < 1 OR batch_size < 1 THEN
        RAISE EXCEPTION 'keep_days and batch_size must be positive';
    END IF;
    -- [왜] 여러 분석이 동시에 시작해도 한 곳만 청소하고 나머지는 기다리지 않고 0을 돌려준다(트랜잭션이 끝나면 풀림)
    -- [주의] React 표(018~020)가 없는 DB(분석 서비스만 준비한 시험 DB)에서는 대화가 프로젝트에 딸렸는지 알 수 없어 아무것도 지우지 않는다
    IF NOT pg_try_advisory_xact_lock(736128) OR to_regclass('public.projects') IS NULL THEN
        RETURN 0;
    END IF;
    -- 1) React 프로젝트: 마지막 활동 = 프로젝트 이름 변경 · 대화 만들기 · run 시작/끝/재개 · 승인 · 견적 중 가장 늦은 시각
    FOR victim IN
        SELECT p.id, p.user_id FROM public.projects p
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
        FOR UPDATE OF p SKIP LOCKED  -- [왜] 지금 run을 시작 · 삭제하는 프로젝트(행 잠금)는 건너뛰고 다음 청소에 맡긴다
    LOOP
        SELECT array_agg(id) INTO ids FROM public.threads WHERE project_id = victim.id;
        -- 같은 UUID의 분석 기록: checkpoint 표 3개(FK 없음) → 분석 thread(메시지 · 승인 기록 · 분석 사건은 cascade) → 남은 thread 없는 회로
        IF to_regclass('sojafit_agent.checkpoints') IS NOT NULL THEN
            DELETE FROM sojafit_agent.checkpoint_writes WHERE thread_id IN (SELECT id::text FROM sojafit_agent.threads WHERE id = ANY(ids) AND user_id = victim.user_id);
            DELETE FROM sojafit_agent.checkpoint_blobs WHERE thread_id IN (SELECT id::text FROM sojafit_agent.threads WHERE id = ANY(ids) AND user_id = victim.user_id);
            DELETE FROM sojafit_agent.checkpoints WHERE thread_id IN (SELECT id::text FROM sojafit_agent.threads WHERE id = ANY(ids) AND user_id = victim.user_id);
        END IF;
        DELETE FROM sojafit_agent.threads WHERE id = ANY(ids) AND user_id = victim.user_id;
        DELETE FROM sojafit_agent.circuits c WHERE c.id = ANY(ids) AND c.user_id = victim.user_id
            AND NOT EXISTS (SELECT 1 FROM sojafit_agent.threads t WHERE t.circuit_id = c.id);
        DELETE FROM public.projects WHERE id = victim.id;  -- 회로 · 대화 · run · 메시지 · 승인 · 견적 · 승인 사례는 FK cascade
        done := done + 1;
    END LOOP;
    -- 2) React 대화에 딸리지 않은 분석 thread(`/api/threads`로 직접 만든 것, 프로젝트가 먼저 지워져 남은 것): thread 자신의 마지막 활동으로 본다
    SELECT array_agg(id) INTO ids FROM (
        SELECT t.id FROM sojafit_agent.threads t
        WHERE NOT EXISTS (SELECT 1 FROM public.threads r WHERE r.id = t.id)
          AND GREATEST(t.created_at,
                (SELECT max(m.created_at) FROM sojafit_agent.messages m WHERE m.thread_id = t.id),
                (SELECT max(e.created_at) FROM sojafit_agent.analysis_events e WHERE e.thread_id = t.id),
                (SELECT max(GREATEST(a.approved_at, a.memory_updated_at)) FROM sojafit_agent.approvals a WHERE a.thread_id = t.id)
              ) < cutoff
        ORDER BY t.created_at, t.id
        LIMIT batch_size
        FOR UPDATE OF t SKIP LOCKED
    ) old;
    IF ids IS NOT NULL THEN
        IF to_regclass('sojafit_agent.checkpoints') IS NOT NULL THEN
            DELETE FROM sojafit_agent.checkpoint_writes WHERE thread_id = ANY(ids::text[]);
            DELETE FROM sojafit_agent.checkpoint_blobs WHERE thread_id = ANY(ids::text[]);
            DELETE FROM sojafit_agent.checkpoints WHERE thread_id = ANY(ids::text[]);
        END IF;
        DELETE FROM sojafit_agent.threads WHERE id = ANY(ids);
        done := done + cardinality(ids);
    END IF;
    -- 3) thread가 하나도 없는 분석 회로(업로드한 넷리스트 원문 포함): 올린 뒤 keep_days일이 지나면 지운다
    DELETE FROM sojafit_agent.circuits WHERE ctid = ANY(ARRAY(
        SELECT c.ctid FROM sojafit_agent.circuits c
        WHERE c.created_at < cutoff AND NOT EXISTS (SELECT 1 FROM sojafit_agent.threads t WHERE t.circuit_id = c.id)
        LIMIT batch_size));
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN done + n;
END $$;

-- 기록 종류: keep_days일이 지난 행을 표마다 최대 batch_size개 지우고 지운 행 수를 돌려준다.
-- 로그인 · 가입 시도 표는 자기 창(15분 · UTC 하루)이 끝나고 잠금도 풀린 행만 지운다(아직 걸린 잠금은 건드리지 않음).
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
    -- [왜] 표마다 ctid(행의 물리 위치) 묶음으로 지워 한 번에 지우는 행 수를 batch_size로 묶는다
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
    RETURN done;
END $$;

REVOKE ALL ON FUNCTION sojafit_agent.purge_inactive_projects(integer, integer), sojafit_agent.purge_log_records(integer, integer) FROM PUBLIC;
DO $$
DECLARE role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('REVOKE ALL ON FUNCTION sojafit_agent.purge_inactive_projects(integer, integer), sojafit_agent.purge_log_records(integer, integer) FROM %I', role_name);
        END IF;
    END LOOP;
END $$;
