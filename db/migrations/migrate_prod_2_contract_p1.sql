-- 운영 DB 이전 2단계 "contract P1"(축소 1): **되돌릴 수 없는 삭제**가 들어 있다. 초안, 아직 어디에도 실행하지 않았다.
--
-- 전제(하나라도 아니면 실행하지 않는다):
--   ① migrate_prod_1_expand.sql을 적용했다
--   ② **P1 새 코드가 배포돼 100%이고** 스모크 28단계가 통과했다. P1 새 코드 = backend/services/quote.py가 approvals의 candidate_part · verdict · part_number 칸을 쓰고,
--      quotes · approved_cases에 snapshot을 쓰지도 읽지도 않으며(승인 사례 목록은 approvals를 JOIN), users.display_name을 참조하지 않는다.
--   ③ 실행 직전 백업을 받았다(1단계 파일 머리 참고).
-- 하는 일: 승인 칸 NOT NULL, 스냅샷 복사본 2개 제거, 앱 JSON 모양을 복제하던 검사를 단순 검사로 교체, 미사용 칸 제거.
-- 분석 서비스(sojafit_agent) 쪽 정리는 코드 변경이 커서 migrate_prod_3_contract_p2.sql로 따로 둔다(P1만 먼저 끝낼 수 있다).
-- 되돌리기: migrate_prod_4_rollback.sql의 B1 절(지운 것은 모두 다른 표의 복사본이거나 미사용이라 무손실).
BEGIN;

-- C0. 옛 코드가 expand 뒤 배포 전까지 넣은 승인 행(새 칸 NULL)을 채우고 NOT NULL로 만든다
UPDATE public.approvals SET
    candidate_part = COALESCE(candidate_part, snapshot #>> '{candidate,part}'),
    verdict        = COALESCE(verdict, snapshot #>> '{candidate,verdict}'),
    part_number    = COALESCE(part_number, snapshot #>> '{candidate,part_number}',
                              regexp_replace(regexp_replace(btrim(snapshot #>> '{candidate,part}'), '^\s*(TSC|Taiwan\s+Semiconductor)\s+', '', 'i'), '\s+', '-', 'g'))
WHERE candidate_part IS NULL OR verdict IS NULL OR part_number IS NULL;
ALTER TABLE public.approvals ALTER COLUMN candidate_part SET NOT NULL, ALTER COLUMN verdict SET NOT NULL, ALTER COLUMN part_number SET NOT NULL;

-- C1. 승인 스냅샷 복사본 제거(견적은 아무도 읽지 않았고, 승인 사례는 이제 approvals를 JOIN해서 읽는다)
ALTER TABLE public.quotes DROP COLUMN snapshot;
ALTER TABLE public.approved_cases DROP COLUMN snapshot;

-- C2. 앱 JSON 모양을 복제하던 검사를 단순 검사로 교체
ALTER TABLE public.runs DROP CONSTRAINT runs_safe_result_check;
ALTER TABLE public.runs RENAME CONSTRAINT ck_runs_safe_result_v2 TO ck_runs_safe_result;
DROP FUNCTION public.conversation_json_matches(jsonb, jsonb);
ALTER TABLE public.projects DROP CONSTRAINT ck_projects_demo;
ALTER TABLE public.projects RENAME CONSTRAINT ck_projects_demo_v2 TO ck_projects_demo;

-- C3. 쓰지 않는 칸
ALTER TABLE public.users DROP COLUMN display_name;

INSERT INTO public.app_migrations (version, note) VALUES ('2026-11-contract-p1', 'migrate_prod_2_contract_p1.sql: 승인 칸 NOT NULL, 스냅샷 복사본 · 미사용 칸 제거, 단순 검사로 교체');
COMMIT;
