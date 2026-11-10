-- 운영 DB 이전 되돌리기: A 절 = expand, B2 절 = contract P2, B1 절 = contract P1을 되돌림(구조 복원 + 복사본 재생성). **적용한 순서의 반대로**(B2 → B1 → A) 한 절씩 실행한다.
-- **초안, 아직 어디에도 실행하지 않았다.** 한 번에 한 절씩, 트랜잭션 하나로 실행한다.
--
-- B 절이 무손실인 이유: contract가 지운 것은 전부 "다른 표의 복사본"(quotes · approved_cases의 snapshot = approvals.snapshot, sojafit_agent.circuits =
-- public.circuits 복사 + 파일 이름 = 프로젝트 이름) 또는 "0행 · 미사용"(sojafit_agent.approvals, users.display_name)이다. 단 contract **이후에 쌓인 데이터**는
-- 복사본을 새로 만들어 채우므로 그대로 복원된다(승인 snapshot은 contract 뒤에도 approvals에 있다).
-- B 절 끝의 "옛 검사 · 옛 청소 함수"는 레포 파일에서 다시 실행한다(아래 셸 명령).

-- ===================================================== B2. contract P2 되돌리기 =====================================================
-- (migrate_prod_3_contract_p2.sql을 적용한 상태에서만. 순서: B2 → B1 → A)
BEGIN;
-- 죽은 승인 표(0행이었음): db/013 + 016의 정의와 같다
CREATE TABLE sojafit_agent.approvals (
    thread_id UUID NOT NULL REFERENCES sojafit_agent.threads(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    approved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    memory_status TEXT NOT NULL DEFAULT 'active' CHECK (memory_status IN ('active', 'revoked', 'deleted')),
    correction TEXT NOT NULL DEFAULT '',
    memory_updated_at TIMESTAMPTZ,
    PRIMARY KEY (thread_id, version)
);

-- 분석 회로 사본: 대화 UUID = 회로 UUID, connections는 public.circuits에서, 파일 이름은 프로젝트 이름에서 다시 만든다(netlist는 원래 빈 글자)
CREATE TABLE sojafit_agent.circuits (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    filename TEXT NOT NULL,
    netlist TEXT NOT NULL,
    connections JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX agent_circuits_owner ON sojafit_agent.circuits (user_id, created_at DESC);
INSERT INTO sojafit_agent.circuits (id, user_id, filename, netlist, connections, created_at)
    SELECT t.id, t.user_id, p.name, '', c.connections, t.created_at
    FROM sojafit_agent.threads t JOIN public.threads pt ON pt.id = t.id
    JOIN public.projects p ON p.id = pt.project_id JOIN public.circuits c ON c.project_id = p.id;
ALTER TABLE sojafit_agent.threads ADD COLUMN circuit_id UUID;
UPDATE sojafit_agent.threads SET circuit_id = id;
ALTER TABLE sojafit_agent.threads ALTER COLUMN circuit_id SET NOT NULL;
ALTER TABLE sojafit_agent.threads ADD CONSTRAINT threads_circuit_id_fkey FOREIGN KEY (circuit_id) REFERENCES sojafit_agent.circuits(id) ON DELETE RESTRICT;
ALTER TABLE sojafit_agent.threads DROP CONSTRAINT threads_user_id_fkey;
ALTER TABLE sojafit_agent.threads ADD CONSTRAINT threads_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

DELETE FROM public.app_migrations WHERE version IN ('2026-11-contract-p2');
COMMIT;
-- 옛 청소 함수(셸에서, 레포 루트): psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/023_retention.sql

-- ===================================================== B1. contract P1 되돌리기 =====================================================
-- (migrate_prod_2_contract_p1.sql을 적용한 상태에서만)
BEGIN;
ALTER TABLE public.users ADD COLUMN display_name VARCHAR(100);

-- 스냅샷 복사본: approvals.snapshot과 같은 내용이라 JOIN으로 다시 채운다
ALTER TABLE public.quotes ADD COLUMN snapshot JSONB;
UPDATE public.quotes q SET snapshot = a.snapshot FROM public.approvals a WHERE a.id = q.approval_id;
ALTER TABLE public.quotes ALTER COLUMN snapshot SET NOT NULL;
ALTER TABLE public.quotes ADD CONSTRAINT quotes_snapshot_check CHECK (jsonb_typeof(snapshot) = 'object' AND NOT quote_snapshot_has_forbidden_key(snapshot));
ALTER TABLE public.approved_cases ADD COLUMN snapshot JSONB;
UPDATE public.approved_cases c SET snapshot = a.snapshot FROM public.approvals a WHERE a.id = c.approval_id;
ALTER TABLE public.approved_cases ALTER COLUMN snapshot SET NOT NULL;
ALTER TABLE public.approved_cases ADD CONSTRAINT approved_cases_snapshot_check CHECK (jsonb_typeof(snapshot) = 'object' AND NOT quote_snapshot_has_forbidden_key(snapshot));

DELETE FROM public.app_migrations WHERE version IN ('2026-11-contract-p1');
COMMIT;

-- ===================================================== A. expand 되돌리기 (마지막) =====================================================
BEGIN;
-- 새 코드가 expand 뒤에 넣은 행(snapshot · circuit_id가 NULL)을 옛 코드가 읽을 수 있게 채운 뒤 NOT NULL을 되돌린다
UPDATE public.quotes q SET snapshot = a.snapshot FROM public.approvals a WHERE a.id = q.approval_id AND q.snapshot IS NULL;
UPDATE public.approved_cases c SET snapshot = a.snapshot FROM public.approvals a WHERE a.id = c.approval_id AND c.snapshot IS NULL;
ALTER TABLE public.quotes ALTER COLUMN snapshot SET NOT NULL;
ALTER TABLE public.approved_cases ALTER COLUMN snapshot SET NOT NULL;
INSERT INTO sojafit_agent.circuits (id, user_id, filename, netlist, connections, created_at)
    SELECT t.id, t.user_id, p.name, '', c.connections, t.created_at
    FROM sojafit_agent.threads t JOIN public.threads pt ON pt.id = t.id
    JOIN public.projects p ON p.id = pt.project_id JOIN public.circuits c ON c.project_id = p.id
    WHERE t.circuit_id IS NULL ON CONFLICT (id) DO NOTHING;
UPDATE sojafit_agent.threads SET circuit_id = id WHERE circuit_id IS NULL;
ALTER TABLE sojafit_agent.threads ALTER COLUMN circuit_id SET NOT NULL;
DROP TRIGGER IF EXISTS trg_threads_purge_checkpoints ON public.threads;
DROP FUNCTION IF EXISTS sojafit_agent.purge_thread_checkpoints();
ALTER TABLE sojafit_agent.threads DROP CONSTRAINT IF EXISTS fk_agent_threads_thread;
ALTER TABLE public.approvals
    DROP CONSTRAINT IF EXISTS ck_approvals_candidate_part, DROP CONSTRAINT IF EXISTS ck_approvals_verdict, DROP CONSTRAINT IF EXISTS ck_approvals_part_number,
    DROP COLUMN IF EXISTS candidate_part, DROP COLUMN IF EXISTS verdict, DROP COLUMN IF EXISTS part_number;
DROP INDEX IF EXISTS public.ix_auth_sessions_user;
DROP INDEX IF EXISTS public.ix_auth_sessions_expires;
ALTER TABLE public.runs DROP CONSTRAINT IF EXISTS ck_runs_safe_result_v2;
ALTER TABLE public.projects DROP CONSTRAINT IF EXISTS ck_projects_demo_v2;
DELETE FROM public.app_migrations WHERE version IN ('2026-11-expand');   -- app_migrations 표 자체는 남긴다(무해)
COMMIT;


-- 옛 JSON 모양 검사와 옛 청소 함수(셸에서, 레포 루트): 함수를 다시 만들고 검사를 다시 건다
--   sed -n '/^CREATE FUNCTION conversation_json_matches/,/^END \$\$;/p' db/019_conversations.sql | psql "$DATABASE_URL" -v ON_ERROR_STOP=1
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/025_runs_safe_result_preferred_mount.sql      # runs_safe_result_check를 최신 모양으로 다시 만든다
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/024_projects_demo_c01.sql                    # ck_projects_demo 6개 이름 목록 검사
-- (ck_runs_safe_result · 새 ck_projects_demo는 옛 검사와 같은 표에 공존해도 무해하다. 정리하려면 DROP CONSTRAINT ck_runs_safe_result;)
