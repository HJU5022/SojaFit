-- 서비스 표 재설계 1/3: 승인 칸 3개 · 스냅샷 복사본 제거 · 단순 CHECK · 세션 인덱스 · 적용 이력 표 (public 표만).
-- 운영 이전용 migrate_prod_1_expand.sql + migrate_prod_2_contract_p1.sql을 **빈 DB 한 번에** 이어 붙인 것이다(구조 결과가 같다는 것은 scripts/db/verify_chain.sh가 확인한다).
-- [왜] 표 이름에 public.을 붙이지 않았다: 시험이 격리 스키마(search_path)에 이 파일을 적용한다(tests/db_schema.py). 일반 DB에서는 search_path가 public이다.
-- [주의] sojafit_agent 쪽(FK · 체크포인트 트리거 · 회로 사본 제거)은 028. 운영 이전의 사전 점검은 뺐다(빈 DB). 백필(E1 UPDATE · C0)은 빈 DB에서 0행이라 그대로 두었다.
-- 되돌리기: 운영 이전 되돌리기 SQL(migrate_prod_4_rollback.sql)은 운영 이전 경로용이다. 새 DB는 볼륨을 지우고 다시 만든다.
-- E1. 승인 JSON 안의 값 3개를 칸으로 꺼낸다(NULL 허용: 옛 코드는 이 칸을 모르고 행을 넣는다. NOT NULL은 contract에서)
ALTER TABLE approvals ADD COLUMN candidate_part TEXT, ADD COLUMN verdict TEXT, ADD COLUMN part_number TEXT;
UPDATE approvals SET
    candidate_part = snapshot #>> '{candidate,part}',
    verdict        = snapshot #>> '{candidate,verdict}',
    -- 식별 품번이 없던 옛 승인: 제조사 이름을 떼고 남은 공백은 '-'(backend/services/quote.py part_number와 같은 규칙)
    part_number    = COALESCE(snapshot #>> '{candidate,part_number}',
                              regexp_replace(regexp_replace(btrim(snapshot #>> '{candidate,part}'), '^\s*(TSC|Taiwan\s+Semiconductor)\s+', '', 'i'), '\s+', '-', 'g'));
ALTER TABLE approvals
    ADD CONSTRAINT ck_approvals_candidate_part CHECK (char_length(candidate_part) BETWEEN 1 AND 100),
    ADD CONSTRAINT ck_approvals_verdict CHECK (verdict IN ('IDENTICAL', 'SPEC_EQUIVALENT', 'ROLE_SUFFICIENT')),
    ADD CONSTRAINT ck_approvals_part_number CHECK (part_number ~ '^[A-Za-z0-9][A-Za-z0-9._+/-]{0,99}$');

-- E1b. 새 코드는 quotes · approved_cases에 snapshot을 쓰지 않는다. contract가 칸을 지울 때까지 NOT NULL이면 새 코드의 INSERT가 실패하므로 NULL을 허용한다
--      (옛 코드는 계속 채운다. CHECK는 NULL을 통과시킨다)
ALTER TABLE quotes ALTER COLUMN snapshot DROP NOT NULL;
ALTER TABLE approved_cases ALTER COLUMN snapshot DROP NOT NULL;

-- E3. 세션 인덱스(계정 삭제의 FK 검사 · 만료 세션 청소)
CREATE INDEX IF NOT EXISTS ix_auth_sessions_user ON auth_sessions (user_id);
CREATE INDEX IF NOT EXISTS ix_auth_sessions_expires ON auth_sessions (expires_at);

-- E4. 단순한 새 검사를 옛 검사 옆에 둔다(옛 것은 contract에서 지우고 이름을 바꾼다)
ALTER TABLE runs ADD CONSTRAINT ck_runs_safe_result_v2 CHECK (safe_result IS NULL OR (jsonb_typeof(safe_result) = 'object'
    AND safe_result ?& ARRAY['answer', 'question_type', 'price_parts', 'interrupt', 'judgement', 'evidence']));
ALTER TABLE projects ADD CONSTRAINT ck_projects_demo_v2 CHECK ((source_kind = 'demo') = (demo_id IS NOT NULL));


-- C0. 옛 코드가 expand 뒤 배포 전까지 넣은 승인 행(새 칸 NULL)을 채우고 NOT NULL로 만든다
UPDATE approvals SET
    candidate_part = COALESCE(candidate_part, snapshot #>> '{candidate,part}'),
    verdict        = COALESCE(verdict, snapshot #>> '{candidate,verdict}'),
    part_number    = COALESCE(part_number, snapshot #>> '{candidate,part_number}',
                              regexp_replace(regexp_replace(btrim(snapshot #>> '{candidate,part}'), '^\s*(TSC|Taiwan\s+Semiconductor)\s+', '', 'i'), '\s+', '-', 'g'))
WHERE candidate_part IS NULL OR verdict IS NULL OR part_number IS NULL;
ALTER TABLE approvals ALTER COLUMN candidate_part SET NOT NULL, ALTER COLUMN verdict SET NOT NULL, ALTER COLUMN part_number SET NOT NULL;

-- C1. 승인 스냅샷 복사본 제거(견적은 아무도 읽지 않았고, 승인 사례는 이제 approvals를 JOIN해서 읽는다)
ALTER TABLE quotes DROP COLUMN snapshot;
ALTER TABLE approved_cases DROP COLUMN snapshot;

-- C2. 앱 JSON 모양을 복제하던 검사를 단순 검사로 교체
ALTER TABLE runs DROP CONSTRAINT runs_safe_result_check;
ALTER TABLE runs RENAME CONSTRAINT ck_runs_safe_result_v2 TO ck_runs_safe_result;
DROP FUNCTION conversation_json_matches(jsonb, jsonb);
ALTER TABLE projects DROP CONSTRAINT ck_projects_demo;
ALTER TABLE projects RENAME CONSTRAINT ck_projects_demo_v2 TO ck_projects_demo;

-- C3. 쓰지 않는 칸
ALTER TABLE users DROP COLUMN display_name;


-- E6. 적용 이력 표(Supabase 도구의 supabase_migrations.schema_migrations와 별개)
CREATE TABLE IF NOT EXISTS app_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    note       TEXT NOT NULL DEFAULT ''
);
ALTER TABLE app_migrations ENABLE ROW LEVEL SECURITY;
INSERT INTO app_migrations (version, note) VALUES ('2026-11-legacy-sql-000-025', '레포 db/000~025 수동 적용분(서비스 표 차이 0, 11-10 확인). 이전 이력은 supabase_migrations.schema_migrations 5건 + 작업 기록');

INSERT INTO app_migrations (version, note) VALUES ('2026-11-expand', 'db/027: 새 칸 · 단순 검사 · 인덱스 추가(빈 DB 한 번에)');
INSERT INTO app_migrations (version, note) VALUES ('2026-11-contract-p1', 'db/027: 승인 칸 NOT NULL, 스냅샷 복사본 · 미사용 칸 제거, 단순 검사로 교체');
