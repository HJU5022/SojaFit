-- 운영 DB 이전 1단계 "expand"(확장): 옛 코드가 돌고 있어도 안전한 변경만 한다. **초안, 아직 어디에도 실행하지 않았다.**
--
-- 순서: ① 백업(아래 명령) → ② 이 파일(expand) → ③ P1 새 코드 배포(0% → 점검 → 100%) → ④ 스모크 · 시험 → ⑤ migrate_prod_2_contract_p1.sql(되돌릴 수 없는 삭제)
--       → ⑥ P2 새 코드 배포 · 점검 → ⑦ migrate_prod_3_contract_p2.sql. (P2 코드가 늦으면 ⑤까지만 하고 멈춰도 된다)
-- 이 파일이 하는 일은 전부 "더하기"다: 새 칸(NULL 허용) · 새 검사(NULL은 통과) · 새 인덱스 · 새 FK(고아 0 확인 뒤) · 이력 표. 옛 코드는 영향이 없다.
-- 되돌리기: migrate_prod_4_rollback.sql의 A 절(이 파일이 만든 것을 지운다).
--
-- 백업(터미널, 정운이 직접. 서비스 표 전부 + 함수. 코퍼스 표(용량이 큼)는 제외. 비밀번호가 든 접속 문자열은 .env에서 읽는다):
-- [주의] 예전 명령은 `-n sojafit_agent`와 `-t`를 함께 써서 -t에 걸린 표만 남고 sojafit_agent가 통째로 빠졌다(pg_dump는 -n과 -t를 교집합으로 본다). 그래서 세 파일로 나눈다.
--   uv run --env-file .env sh -c '
--     T=$(date +%Y%m%d_%H%M)
--     pg_dump "$DATABASE_URL" --no-owner --no-privileges -n sojafit_agent > backup_agent_$T.sql   # sojafit_agent 표 전부(LangGraph 포함) + 데이터 + 함수 · 트리거 함수
--     pg_dump "$DATABASE_URL" --no-owner --no-privileges \
--       -t public.users -t public.auth_sessions -t public.auth_login_attempts -t public.auth_login_ip_attempts \
--       -t public.auth_signup_attempts -t public.auth_google_states -t public.auth_google_pending -t public.auth_google_identities \
--       -t public.projects -t public.circuits -t public.threads -t public.runs -t public.messages -t public.approvals -t public.quotes -t public.approved_cases \
--       > backup_public_tables_$T.sql                                                             # public 서비스 표 + 데이터
--     pg_dump "$DATABASE_URL" --no-owner --no-privileges --schema-only -n public > backup_public_schema_$T.sql   # public 구조만(함수 conversation_json_matches 등 포함, 코퍼스 데이터 없음)'
--   확인: grep -c "CREATE TABLE sojafit_agent\." backup_agent_*.sql 가 0보다 커야 한다(서비스 표 sojafit_agent 5~9개 + LangGraph 표).
--
-- 적용: psql 또는 `uv run --env-file .env python -c "import os,psycopg,sys; c=psycopg.connect(os.environ['DATABASE_URL']); c.execute(open(sys.argv[1]).read()); c.commit()" <이 파일>`
BEGIN;

-- 0. 사전 점검: 하나라도 어긋나면 예외로 전체가 되돌아간다
DO $$
DECLARE n bigint;
BEGIN
    SELECT count(*) INTO n FROM sojafit_agent.threads t WHERE NOT EXISTS (SELECT 1 FROM public.threads p WHERE p.id = t.id);
    IF n > 0 THEN RAISE EXCEPTION 'agent.threads 고아 % 행: 같은 UUID의 public.threads가 없다. FK를 걸기 전에 정리해야 한다', n; END IF;
    SELECT count(*) INTO n FROM public.approvals WHERE snapshot #>> '{candidate,part}' IS NULL OR snapshot #>> '{candidate,verdict}' IS NULL;
    IF n > 0 THEN RAISE EXCEPTION 'approvals % 행의 snapshot에 candidate.part · verdict가 없다', n; END IF;
    SELECT count(*) INTO n FROM public.projects WHERE (source_kind = 'demo') <> (demo_id IS NOT NULL);
    IF n > 0 THEN RAISE EXCEPTION 'projects % 행이 새 검사(데모일 때만 demo_id)에 맞지 않는다', n; END IF;
    SELECT count(*) INTO n FROM public.runs WHERE safe_result IS NOT NULL
        AND NOT (jsonb_typeof(safe_result) = 'object' AND safe_result ?& ARRAY['answer', 'question_type', 'price_parts', 'interrupt', 'judgement', 'evidence']);
    IF n > 0 THEN RAISE EXCEPTION 'runs % 행이 새 검사(필수 키 6개)에 맞지 않는다', n; END IF;
END $$;

-- E1. 승인 JSON 안의 값 3개를 칸으로 꺼낸다(NULL 허용: 옛 코드는 이 칸을 모르고 행을 넣는다. NOT NULL은 contract에서)
ALTER TABLE public.approvals ADD COLUMN candidate_part TEXT, ADD COLUMN verdict TEXT, ADD COLUMN part_number TEXT;
UPDATE public.approvals SET
    candidate_part = snapshot #>> '{candidate,part}',
    verdict        = snapshot #>> '{candidate,verdict}',
    -- 식별 품번이 없던 옛 승인: 제조사 이름을 떼고 남은 공백은 '-'(backend/services/quote.py part_number와 같은 규칙)
    part_number    = COALESCE(snapshot #>> '{candidate,part_number}',
                              regexp_replace(regexp_replace(btrim(snapshot #>> '{candidate,part}'), '^\s*(TSC|Taiwan\s+Semiconductor)\s+', '', 'i'), '\s+', '-', 'g'));
ALTER TABLE public.approvals
    ADD CONSTRAINT ck_approvals_candidate_part CHECK (char_length(candidate_part) BETWEEN 1 AND 100),
    ADD CONSTRAINT ck_approvals_verdict CHECK (verdict IN ('IDENTICAL', 'SPEC_EQUIVALENT', 'ROLE_SUFFICIENT')),
    ADD CONSTRAINT ck_approvals_part_number CHECK (part_number ~ '^[A-Za-z0-9][A-Za-z0-9._+/-]{0,99}$');

-- E1b. 새 코드는 quotes · approved_cases에 snapshot을 쓰지 않는다. contract가 칸을 지울 때까지 NOT NULL이면 새 코드의 INSERT가 실패하므로 NULL을 허용한다
--      (옛 코드는 계속 채운다. CHECK는 NULL을 통과시킨다)
ALTER TABLE public.quotes ALTER COLUMN snapshot DROP NOT NULL;
ALTER TABLE public.approved_cases ALTER COLUMN snapshot DROP NOT NULL;

-- E0. 백업 복원 가능하게: 두 함수가 자기 자신을 스키마 없이 부르는데(재귀) pg_restore는 search_path를 비우고 복원해, 이 함수가 걸린 CHECK(approvals · quotes · runs)의 COPY가
--     'function ... does not exist'로 실패한다. 함수에 search_path를 붙인다(동작 불변, 새 DB 기준선의 quote_snapshot_has_forbidden_key와 같은 설정).
ALTER FUNCTION public.quote_snapshot_has_forbidden_key(jsonb) SET search_path = "$user", public;
ALTER FUNCTION public.conversation_json_matches(jsonb, jsonb) SET search_path = "$user", public;

-- E2. 분석 대화와 화면 대화를 진짜 FK로 잇는다(같은 UUID, 대화를 지우면 분석 기록도 지워짐). 고아 0은 위에서 확인했다
ALTER TABLE sojafit_agent.threads ADD CONSTRAINT fk_agent_threads_thread FOREIGN KEY (id) REFERENCES public.threads(id) ON DELETE CASCADE NOT VALID;
ALTER TABLE sojafit_agent.threads VALIDATE CONSTRAINT fk_agent_threads_thread;
-- 새 코드(P2)는 분석 회로 사본을 만들지 않으므로 circuit_id도 NULL을 허용한다(옛 코드는 계속 채운다)
ALTER TABLE sojafit_agent.threads ALTER COLUMN circuit_id DROP NOT NULL;

-- E3. 세션 인덱스(계정 삭제의 FK 검사 · 만료 세션 청소)
CREATE INDEX IF NOT EXISTS ix_auth_sessions_user ON public.auth_sessions (user_id);
CREATE INDEX IF NOT EXISTS ix_auth_sessions_expires ON public.auth_sessions (expires_at);

-- E4. 단순한 새 검사를 옛 검사 옆에 둔다(옛 것은 contract에서 지우고 이름을 바꾼다)
ALTER TABLE public.runs ADD CONSTRAINT ck_runs_safe_result_v2 CHECK (safe_result IS NULL OR (jsonb_typeof(safe_result) = 'object'
    AND safe_result ?& ARRAY['answer', 'question_type', 'price_parts', 'interrupt', 'judgement', 'evidence']));
ALTER TABLE public.projects ADD CONSTRAINT ck_projects_demo_v2 CHECK ((source_kind = 'demo') = (demo_id IS NOT NULL));

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

-- E6. 적용 이력 표(Supabase 도구의 supabase_migrations.schema_migrations와 별개)
CREATE TABLE IF NOT EXISTS public.app_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    note       TEXT NOT NULL DEFAULT ''
);
ALTER TABLE public.app_migrations ENABLE ROW LEVEL SECURITY;
INSERT INTO public.app_migrations (version, note) VALUES ('2026-11-legacy-sql-000-025', '레포 db/000~025 수동 적용분(서비스 표 차이 0, 11-10 확인). 이전 이력은 supabase_migrations.schema_migrations 5건 + 작업 기록');
INSERT INTO public.app_migrations (version, note) VALUES ('2026-11-expand', 'migrate_prod_1_expand.sql: 새 칸 · FK · 인덱스 · 단순 검사 추가');

-- 확인(0이어야 하는 것 둘, 5여야 하는 것은 아래 읽기 전용 질의로):
--   SELECT count(*) FROM public.approvals WHERE candidate_part IS NULL;   -- 0
--   SELECT conname FROM pg_constraint WHERE conname IN ('fk_agent_threads_thread','ck_runs_safe_result_v2','ck_projects_demo_v2');  -- 3행
COMMIT;
